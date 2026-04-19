"""
Orchestrator — Heron Velocity Engine
Single entry point for the GTM pipeline. Chains the Librarian and Strategist
agents and packages output into a VelocityPack for UI consumption.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agents.librarian import get_technical_fact, LibrarianResponse
from agents.strategist import (
    get_market_narrative,
    TARGET_PERSONA_BRIEFS,
    FIELD_DISPLAY_NAMES,
    MISSION_TO_FIELD,
    ALWAYS_FIELDS,
    RECRUITING_SUB_FIELDS,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Intelligence Triage
# ---------------------------------------------------------------------------

_TRIAGE_SYSTEM = """\
You are the Heron Intelligence Triage agent. Evaluate a news or technical snippet \
against five mission criteria and return a structured priority assessment.

Heron context: 40 GW power electronics, SiC direct MV-to-800V-DC, $140 M Series B, \
products include Heron Link (data-center) and solar/storage inverters.

Criteria:
- GTM               (Market Narrative):    Does this create a LinkedIn / press moment that positions Heron?
- Sales             (Commercial Impact):   Does this create urgency or a new buying trigger for Heron's buyers?
- Recruiting        (Talent/Scale):        Does this signal a scaling inflection that top engineers should hear?
- Tech One-Pager    (Technical Briefing):  Does this surface new specs or data that should update partner/investor technical docs?
- Customer Collateral (Business Case):     Does this sharpen the ROI or competitive argument for customer-facing materials?

Return ONLY a valid JSON object. Each mission key maps to an object or null (if not applicable):

{{
  "GTM": {{
    "rationale": "<one sentence — must cite a specific mechanism or number from the snippet>",
    "priority": "P1" | "P2" | "P3",
    "strategic_rationale": "<one sentence — WHY this priority level was assigned>"
  }},
  "Sales": {{
    "rationale": "<one sentence>",
    "priority": "P1" | "P2" | "P3",
    "strategic_rationale": "<one sentence>"
  }},
  "Recruiting": {{
    "rationale": "<one sentence>",
    "priority": "P1" | "P2" | "P3",
    "strategic_rationale": "<one sentence>"
  }},
  "Tech One-Pager": {{
    "rationale": "<one sentence>",
    "priority": "P1" | "P2" | "P3",
    "strategic_rationale": "<one sentence>"
  }},
  "Customer Collateral": {{
    "rationale": "<one sentence>",
    "priority": "P1" | "P2" | "P3",
    "strategic_rationale": "<one sentence>"
  }}
}}

Priority rules — assign exactly one level per mission:
- "P1" CRITICAL: The snippet directly, urgently triggers this mission. Time-sensitive: competitor \
announcement, regulation deadline, major scale milestone, or direct Heron technical spec match. \
Assign sparingly — only when immediate action is warranted.
- "P2" RELEVANT: Useful market context worth acting on. Not time-critical. Standard recommendation.
- "P3" INFORMATIONAL: Loosely related context; no immediate mission response needed. \
Example: Recruiting is relevant but the snippet is only a minor competitor software update \
with no talent signal.

Omit a mission entirely (set to null) if the signal is negligible or absent.
strategic_rationale must explain the priority assignment in one concrete sentence.\
"""

_TRIAGE_HUMAN = "News / technical snippet:\n{text}"


@dataclass
class TriageRecommendation:
    rationale: str
    priority: str               # "P1" | "P2" | "P3"
    strategic_rationale: str    # why this priority level was assigned


@dataclass
class TriageResult:
    """Structured output from the pre-scan triage agent."""
    recommendations: dict[str, TriageRecommendation]   # mission label → rich assessment


_NULL_STRINGS = {"null", "none", "n/a", ""}

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _parse_triage_json(raw: str | None) -> dict:
    """
    Strip markdown fences and parse JSON from a triage LLM response.

    Returns an empty dict on any failure so callers never receive None.
    """
    if not raw:
        return {}
    # Strip ``` fences if present
    match = _FENCE_RE.match(raw.strip())
    cleaned = match.group(1) if match else raw.strip()
    # Pass 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Pass 2: slice from first { to last }
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def _coerce_str(value: object, default: str) -> str:
    """Return a lower-cased string, substituting default for null-like values."""
    s = str(value).strip().lower() if value is not None else ""
    return default if s in _NULL_STRINGS else s


def triage_news(text: str) -> TriageResult:
    """
    Run a fast LLM pre-scan of a news snippet against four mission criteria.

    Uses gpt-4o-mini with JSON mode for speed and low cost. Returns only
    missions with a genuine signal; null / weak entries are filtered out.
    Always returns a valid TriageResult — never raises or returns None.

    Args:
        text: Raw news snippet or technical update from the user.

    Returns:
        TriageResult with a recommendations dict (mission → TriageRecommendation).
    """
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", _TRIAGE_SYSTEM),
        ("human", _TRIAGE_HUMAN),
    ])

    try:
        result = (prompt | llm).invoke({"text": text})
        raw_content: str | None = getattr(result, "content", None)
        data = _parse_triage_json(raw_content)
    except Exception:
        return TriageResult(recommendations={})

    recommendations: dict[str, TriageRecommendation] = {}
    for mission, payload in data.items():
        if not payload or not isinstance(payload, dict):
            continue
        if mission not in MISSION_TO_FIELD:
            continue

        rationale = str(payload.get("rationale") or "").strip()
        if not rationale or rationale.lower() in _NULL_STRINGS:
            continue

        # Normalise priority: accept P1/P2/P3 (case-insensitive); default P2
        raw_priority = str(payload.get("priority") or "").strip().upper()
        priority = raw_priority if raw_priority in ("P1", "P2", "P3") else "P2"

        strategic_rationale = str(payload.get("strategic_rationale") or "").strip()

        recommendations[mission] = TriageRecommendation(
            rationale=rationale,
            priority=priority,
            strategic_rationale=strategic_rationale,
        )

    return TriageResult(recommendations=recommendations)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class VelocityPack:
    user_input: str
    technical_facts: str
    confidence: int
    narratives: dict[str, str]         # field key → content
    selected_missions: list[str]       # mission labels chosen by the user
    needs_review: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __str__(self) -> str:
        review_flag = "[NEEDS REVIEW]" if self.needs_review else "[CLEARED]"
        sep = "=" * 72
        thin = "-" * 72
        parts = [
            sep,
            f"VELOCITY PACK  {review_flag}  |  {self.timestamp}",
            sep,
            f"INPUT:          {self.user_input}",
            f"MISSIONS:       {', '.join(self.selected_missions)}",
            f"CONFIDENCE:     {self.confidence}/100"
            + ("  <-- low confidence; verify before use" if self.needs_review else ""),
            thin,
            f"TECHNICAL FACTS:\n{self.technical_facts}",
            thin,
        ]
        for fld, content in self.narratives.items():
            label = FIELD_DISPLAY_NAMES.get(fld, fld)
            parts.append(f"NARRATIVE [{label}]:\n{content}")
            parts.append(thin)
        parts.append(sep)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_velocity_pipeline(
    user_input: str,
    target_persona: str | None = None,
    selected_missions: list[str] | None = None,
) -> VelocityPack:
    """
    Run the full Heron GTM pipeline for a given query.

    Step 1 — Librarian: grounds the user query against the SST-V2 spec and
              computes a confidence score via claim-grounding formula.
    Step 2 — Strategist: generates outputs only for the selected missions,
              keeping the prompt and LLM cost proportional to the selection.

    Args:
        user_input:         Technical question or news snippet.
        target_persona:     Candidate persona for the Talent Acquisition Suite.
        selected_missions:  Subset of ["GTM", "Sales", "Recruiting", "Tech One-Pager",
                            "Customer Collateral"]. If None or empty, all missions are generated.

    Returns:
        VelocityPack with grounded facts, confidence score, selected narrative
        outputs, and a needs_review flag (True when confidence < 80).
    """
    # Convert mission labels to field keys
    resolved_missions = selected_missions or list(MISSION_TO_FIELD.keys())
    selected_fields = [
        MISSION_TO_FIELD[m] for m in resolved_missions if m in MISSION_TO_FIELD
    ]

    # Step 1 — Librarian
    lib_response: LibrarianResponse = get_technical_fact(user_input)

    # Step 2 — Strategist (only for selected fields + always-fields).
    # JSON fence-stripping happens inside strategist._parse_json_response.
    # The outer try/except ensures a malformed LLM response never crashes the pipeline.
    _MISSION_FIELDS = (
        "EXTERNAL_GTM", "LINKEDIN_POST", "MARKETING_ARTICLE",
        "SALES_BATTLECARD",
        "OUTREACH_HOOK", "COMPANY_PITCH", "ROLE_REQUIREMENTS",
        "SCREENING_GUIDE", "KEY_TALKING_POINTS",
        "TECH_ONE_PAGER", "CUSTOMER_COLLATERAL",
    )
    _ALWAYS_FIELD_KEYS = ("VISUAL_DIRECTIVES", "TECHNICAL_SCHEMATIC")
    try:
        narratives: dict[str, str] = get_market_narrative(
            technical_context=lib_response.answer,
            librarian_score=lib_response.confidence,
            target_persona=target_persona,
            selected_fields=selected_fields if selected_fields else None,
        )
    except Exception as exc:
        # Return safe empty narratives so the UI degrades gracefully
        narratives = {k: "" for k in _MISSION_FIELDS + _ALWAYS_FIELD_KEYS}
        narratives["_error"] = str(exc)

    # Belt-and-suspenders: ensure every mission key is present (strategist also does this).
    # Social and recruiting sub-keys must be clean strings — clear LLM error placeholders.
    for _k in _MISSION_FIELDS:
        narratives.setdefault(_k, "")
    for _clean_key in ("LINKEDIN_POST", "MARKETING_ARTICLE") + tuple(RECRUITING_SUB_FIELDS):
        if narratives.get(_clean_key, "").startswith("["):
            narratives[_clean_key] = ""

    return VelocityPack(
        user_input=user_input,
        technical_facts=lib_response.answer,
        confidence=lib_response.confidence,
        narratives=narratives,
        selected_missions=resolved_missions,
        needs_review=lib_response.confidence < 80,
    )


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cases = [
        (
            "What is the efficiency, footprint reduction, and legacy equipment eliminated by Heron Link?",
            ["GTM", "Sales"],
        ),
        (
            "What are the reliability, NPV impact, and warranty terms for the solar product?",
            ["Recruiting", "Customer Collateral"],
        ),
    ]

    for query, missions in cases:
        pack = run_velocity_pipeline(query, selected_missions=missions)
        print(pack)
        print()
