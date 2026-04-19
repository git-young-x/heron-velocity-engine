"""
Librarian Agent — Heron Velocity Engine
Answers technical questions about Heron Link by grounding responses
exclusively in the SST-V2 specification document.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPECS_PATH = Path(__file__).parent.parent / "data" / "heron_specs.txt.txt"

SYSTEM_PROMPT = """You are the Lead Power Electronics Engineer at Heron Power. \
You authored the Single Source of Truth (SST-V2) specification document. \
Your answers are precise, direct, and free of marketing fluff or padding.

RULES:
1. Base your answer ONLY on the provided specification text.
2. If the answer is explicitly stated in the spec, Confidence Score = 70–100 \
   (scale with how directly the spec addresses the question).
3. If the answer requires inference or is not covered by the spec, \
   Confidence Score = 0–49. State clearly what is missing.
4. Never fabricate numbers, claims, or capabilities not present in the spec.
5. Output format — respond with EXACTLY this structure, no extra text before or after:

ANSWER: <your direct technical answer>
CONFIDENCE: <integer 0-100>
BASIS: <1–2 sentences citing the specific spec section(s) used, or stating what is absent>"""

HUMAN_PROMPT = """SPECIFICATION DOCUMENT:
{spec_text}

QUERY: {query}"""

# Used when the input is a scraped news article rather than a direct query
URL_SYSTEM_PROMPT = """You are the Lead Power Electronics Engineer at Heron Power. \
You authored the Single Source of Truth (SST-V2) specification document. \
Your answers are precise, direct, and free of marketing fluff or padding.

RULES:
1. You are given a news article and the SST-V2 specification.
2. Identify which claims, trends, or developments in the article are directly \
   supported, contradicted, or absent from the Heron spec.
3. Summarise the relationship between the article's news and Heron's capabilities.
4. Confidence Score reflects how directly the spec speaks to the article's key claims \
   (70–100 = well-covered, 50–69 = partially covered, 0–49 = little/no coverage).
5. Never fabricate numbers or capabilities not present in the spec.
6. Output format — respond with EXACTLY this structure, no extra text before or after:

ANSWER: <your analysis of how the article relates to Heron's specs>
CONFIDENCE: <integer 0-100>
BASIS: <1–2 sentences citing the specific spec section(s) used, or stating what is absent>"""

URL_HUMAN_PROMPT = """SPECIFICATION DOCUMENT:
{spec_text}

NEWS ARTICLE (scraped from {url}):
{article_text}"""


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

@dataclass
class LibrarianResponse:
    query: str
    answer: str
    confidence: int
    basis: str

    def __str__(self) -> str:
        bar = "#" * (self.confidence // 10) + "-" * (10 - self.confidence // 10)
        status = "GROUNDED" if self.confidence >= 50 else "INFERRED/ABSENT"
        return (
            f"ANSWER:     {self.answer}\n"
            f"CONFIDENCE: [{bar}] {self.confidence}/100  ({status})\n"
            f"BASIS:      {self.basis}"
        )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _is_url(text: str) -> bool:
    return text.strip().startswith("http://") or text.strip().startswith("https://")


def _scrape_url(url: str) -> str:
    """
    Fetch a URL and extract the main readable text using BeautifulSoup.
    Strips scripts, styles, and navigation boilerplate.

    Returns:
        Extracted article text (may be truncated to ~8 000 chars to stay within
        token limits).

    Raises:
        RuntimeError: If the page cannot be fetched or no text is found.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HeronVelocityEngine/1.0)"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch URL '{url}': {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    # Prefer <article> body; fall back to <body>
    container = soup.find("article") or soup.find("main") or soup.body
    if container is None:
        raise RuntimeError(f"No readable content found at '{url}'.")

    text = container.get_text(separator="\n", strip=True)

    if not text.strip():
        raise RuntimeError(f"Scraped text is empty for '{url}'.")

    # Truncate to ~8 000 chars to avoid blowing the context window
    return text[:8_000]


def _load_spec() -> str:
    """Load the Heron SST-V2 spec from disk."""
    if not SPECS_PATH.exists():
        raise FileNotFoundError(f"Spec file not found: {SPECS_PATH}")
    loader = TextLoader(str(SPECS_PATH), encoding="utf-8")
    docs = loader.load()
    return "\n".join(doc.page_content for doc in docs)


def _parse_response(raw: str, query: str) -> LibrarianResponse:
    """Extract structured fields from the LLM response."""
    answer_match = re.search(r"ANSWER:\s*(.+?)(?=\nCONFIDENCE:)", raw, re.DOTALL)
    confidence_match = re.search(r"CONFIDENCE:\s*(\d+)", raw)
    basis_match = re.search(r"BASIS:\s*(.+)", raw, re.DOTALL)

    answer = answer_match.group(1).strip() if answer_match else raw.strip()
    basis = basis_match.group(1).strip() if basis_match else "Basis not parsed."

    try:
        confidence = int(confidence_match.group(1)) if confidence_match else 0
        confidence = max(0, min(100, confidence))
    except (ValueError, AttributeError):
        confidence = 0

    return LibrarianResponse(query=query, answer=answer, confidence=confidence, basis=basis)


_GROUNDING_CHECK_SYSTEM = """\
You are a technical fact-grounding analyst. Given an INPUT TEXT and a SPECIFICATION DOCUMENT:

1. Extract every specific technical claim from INPUT TEXT — numbers, specs, product capabilities, performance figures.
2. For each claim, determine whether the SPECIFICATION DOCUMENT explicitly supports, confirms, or states it.

A claim is "grounded" only if the spec directly mentions or confirms it.
Inferred or implied claims are NOT grounded.

Return ONLY valid JSON — no prose before or after:
{{
  "total_claims": <integer>,
  "grounded_claims": <integer>,
  "claims": [
    {{"claim": "<brief description>", "grounded": true}}
  ]
}}

If the input text has no specific technical claims, return: {{"total_claims": 0, "grounded_claims": 0, "claims": []}}\
"""

_GROUNDING_CHECK_HUMAN = """\
SPECIFICATION DOCUMENT:
{spec_text}

INPUT TEXT:
{input_text}\
"""


def _grounding_check(input_text: str, spec_text: str) -> int:
    """
    Run a claim-extraction + grounding pass against the spec.

    Returns:
        Confidence score 0–100 based on (grounded_claims / total_claims).
        Returns 50 if no claims are found (neutral, not zero).
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", _GROUNDING_CHECK_SYSTEM),
        ("human", _GROUNDING_CHECK_HUMAN),
    ])
    try:
        result = (prompt | llm).invoke({
            "spec_text": spec_text,
            "input_text": input_text[:4_000],  # cap to avoid token blow-out
        })
        import json as _json
        data = _json.loads(result.content)
        total = int(data.get("total_claims", 0))
        grounded = int(data.get("grounded_claims", 0))
        if total == 0:
            return 50
        score = round(grounded / total * 100)
        return max(0, min(100, score))
    except Exception:
        return 50


def get_technical_fact(query: str) -> LibrarianResponse:
    """
    Query the Heron SST-V2 specification and return a grounded technical answer.

    Confidence is computed by a two-pass grounding check:
    score = (grounded claims / total claims identified) * 100.

    If `query` starts with 'http', the URL is scraped and the Librarian analyses
    how the article's news relates to Heron's specifications.

    Args:
        query: A technical question OR a URL to a news article.

    Returns:
        LibrarianResponse with answer, confidence score (0-100), and source basis.
        Confidence < 50 means the answer is not explicitly in the spec.

    Raises:
        RuntimeError: If a URL is provided but cannot be fetched.
    """
    spec_text = _load_spec()

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    if _is_url(query):
        article_text = _scrape_url(query)
        prompt = ChatPromptTemplate.from_messages([
            ("system", URL_SYSTEM_PROMPT),
            ("human", URL_HUMAN_PROMPT),
        ])
        chain = prompt | llm
        result = chain.invoke({
            "spec_text": spec_text,
            "url": query.strip(),
            "article_text": article_text,
        })
        grounding_input = article_text
    else:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])
        chain = prompt | llm
        result = chain.invoke({"spec_text": spec_text, "query": query})
        grounding_input = query

    parsed = _parse_response(result.content, query)

    # Replace LLM self-reported confidence with grounded formula score
    parsed.confidence = _grounding_check(grounding_input, spec_text)

    return parsed


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_queries = [
        "What is the peak efficiency of Heron Link for data centers?",
        "What switching frequency do the planar magnetics operate at?",
        "What is the operating temperature range of Heron Link?",  # not in spec
    ]

    for q in test_queries:
        print(f"\n{'='*72}")
        print(f"QUERY: {q}")
        print("-" * 72)
        response = get_technical_fact(q)
        print(response)

    print(f"\n{'='*72}")
