"""
Heron Velocity Engine — Command Center UI
"""

import streamlit as st

from agents.orchestrator import run_velocity_pipeline, VelocityPack, triage_news, TriageResult, TriageRecommendation
from agents.strategist import TARGET_PERSONA_BRIEFS, RECRUITING_SUB_FIELDS

# Mandate 4: MISSION_TO_FIELD defined locally — identical to agents/strategist.py.
# Kept here to be independent of import chain failures.
MISSION_TO_FIELD: dict[str, str] = {
    "GTM":                "EXTERNAL_GTM",
    "Sales":              "SALES_BATTLECARD",
    "Recruiting":         "RECRUITING_HOOK",
    "Tech One-Pager":     "TECH_ONE_PAGER",
    "Customer Collateral": "CUSTOMER_COLLATERAL",
}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Heron Velocity Engine",
    page_icon="⚡",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Command Center CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Typography ──────────────────────────────────────────────── */
html, body, [class*="css"], .stMarkdown p, .stMarkdown li,
.stMarkdown td, .stMarkdown th, label, .stSelectbox label,
.stTextArea label, .stMultiSelect label, button, input, textarea, select {
    font-family: 'Inter', 'Segoe UI', 'Roboto', 'Helvetica Neue', sans-serif !important;
}

/* ── Global Background (#FDFDFD) ─────────────────────────────── */
.stApp,
[data-testid="stAppViewContainer"],
section[data-testid="stMain"] {
    background-color: #FDFDFD !important;
}

/* ── Content width — strict 900px centered ───────────────────── */
.main .block-container {
    max-width: 900px !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* ── Sidebar — Deep Navy (#002D5B) ───────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #002D5B !important;
    border-right: none !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
    letter-spacing: 0.02em;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown li,
[data-testid="stSidebar"] .stMarkdown strong {
    color: #C5D8F0 !important;
}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextArea label,
[data-testid="stSidebar"] .stMultiSelect label {
    color: #A8C4DF !important;
    font-size: 0.82rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}
[data-testid="stSidebar"] hr { border-color: #1A4A7A !important; }

/* Sidebar text area */
[data-testid="stSidebar"] textarea {
    background-color: #003A74 !important;
    border: 1px solid #1A5AA0 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
    caret-color: #FFFFFF;
}
[data-testid="stSidebar"] textarea:focus {
    border-color: #007BFF !important;
    box-shadow: 0 0 0 3px rgba(0,123,255,0.2) !important;
    outline: none !important;
}
[data-testid="stSidebar"] textarea::placeholder { color: #5A82A8 !important; }

/* Sidebar selectbox */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #003A74 !important;
    border: 1px solid #1A5AA0 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] div {
    color: #FFFFFF !important;
}

/* Sidebar multiselect container */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] > div {
    background-color: #003A74 !important;
    border: 1px solid #1A5AA0 !important;
    border-radius: 8px !important;
}

/* ── Tab bar ──────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #F0F4F8;
    border-radius: 10px;
    padding: 4px 6px;
    gap: 4px;
    border: 1px solid #E0E0E0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    padding: 8px 18px;
    font-weight: 500;
    font-size: 13px;
    color: #5A6A7A;
    transition: all 0.15s ease;
}
.stTabs [aria-selected="true"] {
    background-color: #E3F2FD !important;
    color: #007BFF !important;
    font-weight: 600;
}

/* ── Cards — white bg, faint border, subtle shadow ───────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #EEEEEE !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    padding: 4px 8px !important;
}

/* ── Markdown — primary charcoal (#1A1C1E) ───────────────────── */
.stMarkdown h1 { color: #002D5B !important; font-weight: 700; margin-bottom: 12px; }
.stMarkdown h2 { color: #002D5B !important; }
.stMarkdown h3 {
    color: #002D5B;
    font-size: 1.05rem;
    font-weight: 600;
    margin-top: 20px;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid #E8EDF2;
}
.stMarkdown h3:first-child { margin-top: 4px; }
.stMarkdown strong { color: #1A1C1E; }
.stMarkdown p { color: #1A1C1E; line-height: 1.75; margin-bottom: 10px; }
.stMarkdown li { color: #3D4A58; line-height: 1.75; margin-bottom: 6px; }
.stMarkdown ul { padding-left: 20px; }
.stMarkdown hr { border-color: #E8EDF2; margin: 18px 0; }

/* ── Tables — navy header, clean lines ───────────────────────── */
.stMarkdown table {
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0;
    font-size: 13.5px;
    border: 1px solid #E8EDF2;
    border-radius: 8px;
    overflow: hidden;
}
.stMarkdown thead th {
    background-color: #EBF3FF;
    color: #002D5B;
    font-weight: 600;
    padding: 10px 14px;
    border-bottom: 2px solid #C8DDEF;
    text-align: left;
}
.stMarkdown tbody td {
    padding: 9px 14px;
    border-bottom: 1px solid #F0F4F8;
    color: #1A1C1E;
    background-color: #FFFFFF;
}
.stMarkdown tbody tr:last-child td { border-bottom: none; }
.stMarkdown tbody tr:hover td { background-color: #F5F9FF; }

/* ── Expander ────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background-color: #FFFFFF;
    border: 1px solid #E0E0E0 !important;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #1A1C1E;
}

/* ── Primary buttons — Electric Blue (#007BFF) ───────────────── */
.stButton > button[kind="primary"] {
    background-color: #007BFF !important;
    border: none !important;
    color: #FFFFFF !important;
    font-weight: 600;
    border-radius: 8px;
    transition: all 0.2s ease;
}
.stButton > button[kind="primary"]:hover {
    background-color: #0062CC !important;
    box-shadow: 0 4px 12px rgba(0,123,255,0.3) !important;
}

/* Secondary / triage button (non-primary) */
.stButton > button:not([kind="primary"]) {
    background-color: #FFFFFF !important;
    border: 1px solid #C8D8E8 !important;
    color: #002D5B !important;
    border-radius: 8px;
    font-weight: 500;
}
.stButton > button:not([kind="primary"]):hover {
    background-color: #EBF3FF !important;
    border-color: #007BFF !important;
}

/* ── Main-area text inputs ───────────────────────────────────── */
textarea, .stTextArea textarea {
    background-color: #FFFFFF !important;
    border: 1px solid #E0E0E0 !important;
    border-radius: 8px !important;
    color: #1A1C1E !important;
}
textarea:focus, .stTextArea textarea:focus {
    border-color: #007BFF !important;
    box-shadow: 0 0 0 3px rgba(0,123,255,0.15) !important;
    outline: none !important;
}

/* ── Multiselect chips — scoped to .stMultiSelect for max specificity ── */
.stMultiSelect div[data-baseweb="tag"] {
    background-color: #E3F2FD !important;
    border: 1px solid #007BFF !important;
    border-radius: 6px !important;
}
.stMultiSelect div[data-baseweb="tag"] span {
    color: #002D5B !important;
    font-weight: 700 !important;
}
.stMultiSelect div[data-baseweb="tag"] svg {
    fill: #002D5B !important;
}
.stMultiSelect div[data-baseweb="tag"]:hover {
    background-color: #BBDEFB !important;
}

/* ── Main-area selectbox ─────────────────────────────────────── */
.main [data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1px solid #E0E0E0 !important;
    border-radius: 8px !important;
    color: #1A1C1E !important;
}

/* ── Metrics ─────────────────────────────────────────────────── */
[data-testid="stMetricLabel"] { font-size: 12px; color: #5A6A7A; }
[data-testid="stMetricValue"] { color: #002D5B; font-weight: 600; }

/* ── Alerts ──────────────────────────────────────────────────── */
.stAlert { border-radius: 8px; }

/* ── Page header — white + Electric Blue top accent line ─────── */
.hve-header {
    padding: 28px 0 16px 0;
    border-top: 3px solid #007BFF;
    border-bottom: 1px solid #E8EDF2;
    margin-bottom: 28px;
    background-color: #FFFFFF;
}
.hve-header h1 {
    font-size: 1.85rem;
    font-weight: 700;
    color: #002D5B;
    margin: 0;
    letter-spacing: -0.02em;
}
.hve-header p {
    color: #5A6A7A;
    font-size: 0.82rem;
    margin: 6px 0 0 0;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ── Intelligence Executive Summary banner ───────────────────── */
.hve-triage-banner {
    background: linear-gradient(135deg, #EBF5FF 0%, #F0F7FF 100%);
    border: 1px solid #C8DDEF;
    border-left: 4px solid #007BFF;
    border-radius: 10px;
    padding: 16px 22px 10px 22px;
    margin-bottom: 6px;
}
.hve-triage-banner .label {
    color: #002D5B;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 4px 0;
}
.hve-triage-banner .sub {
    color: #3D4A58;
    font-size: 0.83rem;
    margin: 0 0 14px 0;
}

/* ── Kill native Streamlit top bar & all black remnants ──────── */
/* Body-level default — prevents Streamlit dark-mode bleed */
body { background-color: #FFFFFF !important; }
/* Decoration ribbon (coloured bar at very top of viewport) */
[data-testid="stDecoration"] { display: none !important; }
/* Top header bar */
header[data-testid="stHeader"],
.stApp > header,
[data-testid="stHeader"] {
    background-color: #FFFFFF !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
/* Toolbar / action icons row */
[data-testid="stToolbar"] { background-color: #FFFFFF !important; }
/* Any remaining stApp-level backgrounds */
.stApp { background-color: #FDFDFD !important; }

/* ── st.warning / st.info / st.error — force charcoal text ─────  */
/* Broad container catch (covers all notification kinds) */
div[data-testid="stNotification"],
div[data-testid="stNotification"] p,
div[data-testid="stNotification"] span,
div[data-testid="stNotification"] strong,
/* Kind-specific containers */
div[data-testid="stNotificationContentWarning"],
div[data-testid="stNotificationContentWarning"] p,
div[data-testid="stNotificationContentWarning"] span,
div[data-testid="stNotificationContentWarning"] strong,
div[data-testid="stNotificationContentInfo"],
div[data-testid="stNotificationContentInfo"] p,
div[data-testid="stNotificationContentInfo"] span,
/* Generic alert role catch */
div[role="alert"] p,
div[role="alert"] span,
div[role="alert"] strong { color: #1A1C1E !important; }

/* ── st.status container ─────────────────────────────────────── */
[data-testid="stStatusWidget"] {
    border: 1px solid #C8DDEF !important;
    border-radius: 10px !important;
    background-color: #F5F9FF !important;
}
[data-testid="stStatusWidget"] p,
[data-testid="stStatusWidget"] span { color: #1A1C1E !important; }

/* ── Input border transition (Electric Blue on focus) ────────── */
textarea, .stTextArea textarea {
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

/* ── Primary button — tactile lift on hover ──────────────────── */
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0px);
    box-shadow: none !important;
}

/* ── Customer Collateral CTA block ───────────────────────────── */
.hve-cta {
    text-align: center;
    margin: 28px auto 8px auto;
    padding: 16px 32px;
    background: linear-gradient(135deg, #007BFF 0%, #0062CC 100%);
    border-radius: 10px;
    font-weight: 600;
    font-size: 1rem;
    color: #FFFFFF !important;
    max-width: 520px;
}
.hve-cta * { color: #FFFFFF !important; }

/* ── Priority badges ─────────────────────────────────────────── */
.hve-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1.6;
}
.hve-badge-p1 { background: #DC3545; color: #FFFFFF !important; }
.hve-badge-p2 { background: #FFC107; color: #1A1C1E !important; }
.hve-badge-p3 { background: #28A745; color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state — initialize once so nothing downstream reads an unset key.
# Also sanitize any stale values left by previous code versions.
# ---------------------------------------------------------------------------

_VALID_MISSIONS = list(MISSION_TO_FIELD.keys())

if "triage" not in st.session_state:
    st.session_state["triage"] = None
if "pack" not in st.session_state:
    st.session_state["pack"] = None
if "target_persona" not in st.session_state:
    st.session_state["target_persona"] = "Hardware/Power Electronics"

# Sanitize mission_selection: strip any values that aren't valid mission labels
# (e.g. field keys like "RECRUITING_HOOK" left by an older code version).
raw_selection = st.session_state.get("mission_selection", ["GTM"])
clean_selection = [m for m in raw_selection if m in _VALID_MISSIONS]
st.session_state["mission_selection"] = clean_selection if clean_selection else ["GTM"]

# Same sanitize for selected_missions (stored after a Generate run)
raw_sm = st.session_state.get("selected_missions", [])
st.session_state["selected_missions"] = [m for m in raw_sm if m in _VALID_MISSIONS]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ROLE_LOGIC: dict[str, str] = {
    "Hardware/Power Electronics": (
        "Market demand for higher power density puts the hardware design constraint center-stage. "
        "**Hardware/Power Electronics** engineers own SiC device selection, magnetic design, "
        "and thermal stack. At 63kW dissipation per 4.2MW unit, thermal budget is the "
        "constraint everything else is subordinate to. At 40GW, every design decision ships at scale."
    ),
    "Firmware/Software": (
        "Software-defined power architecture is the unlock for production yield at scale. "
        "**Firmware/Software** engineers own deterministic RTOS control loops and nanosecond "
        "gate-drive sequences at 1.2kV SiC — code where 1µs of dead-time optimization "
        "is a yield gain across thousands of units, not a patch."
    ),
    "Grid Integration/Utilities": (
        "Interconnection queues are accelerating pressure on developers and utilities. "
        "**Grid Integration** engineers own active harmonic filter algorithms and "
        "IEEE 1547-2018 compliance logic — the code that lets Heron talk to the grid "
        "on Heron's terms. At 40GW, that is writing the compliance standard, not meeting it."
    ),
    "Supply Chain/Operations": (
        "Building 40GW of power infrastructure requires supply chains that don't exist yet. "
        "**Supply Chain/Operations** leads own SiC module qualification, second-source "
        "development, and BoM simplification — every transformer Heron eliminates is a "
        "supplier relationship that doesn't need to exist. Lead time is the product moat."
    ),
}

# ---------------------------------------------------------------------------
# GTM Multi-Pillar Suite renderer
# ---------------------------------------------------------------------------

_GTM_PILLAR_CAPTIONS: dict[str, str] = {
    "🎯 Campaign Launcher":    "Channel strategy, killer visual concept, and hero copy for this GTM push.",
    "📜 Technical One-Pager": "Hard-spec bullets for partner and investor briefings.",
    "💡 Market Education":    "Legacy Architecture vs. Heron — feature-by-feature comparison.",
}


def _render_market_education(body: str) -> None:
    """Render the 💡 Market Education pillar as a 3-column feature table."""
    import re as _re

    def _parse_bullets(text: str) -> tuple[dict[str, str], str]:
        rows: dict[str, str] = {}
        summary_parts: list[str] = []
        past_bullets = False
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:]
                if ": " in item:
                    k, v = item.split(": ", 1)
                    rows[k.strip()] = v.strip()
                past_bullets = True
            elif past_bullets and stripped:
                summary_parts.append(stripped)
        return rows, "\n".join(summary_parts)

    parts = _re.split(r"\*\*Heron Architecture\*\*", body, maxsplit=1)
    if len(parts) == 2:
        legacy_raw = parts[0].replace("**Legacy Architecture**", "").strip()
        heron_raw = parts[1].strip()
        legacy_data, _ = _parse_bullets(legacy_raw)
        heron_data, summary = _parse_bullets(heron_raw)
        features = list(dict.fromkeys(list(legacy_data.keys()) + list(heron_data.keys())))

        if features:
            h1, h2, h3 = st.columns([1, 2, 2])
            with h1:
                st.markdown("**Feature**")
            with h2:
                st.markdown("**🏗️ Legacy**")
            with h3:
                st.markdown("**⚡ Heron**")
            st.markdown("---")
            for feat in features:
                c1, c2, c3 = st.columns([1, 2, 2])
                with c1:
                    st.markdown(f"**{feat}**")
                with c2:
                    st.markdown(legacy_data.get(feat, "—"))
                with c3:
                    st.markdown(heron_data.get(feat, "—"))
        else:
            st.markdown(body)
            return

        if summary:
            st.markdown("")
            st.caption(summary)
    else:
        st.markdown(body)


def _render_social_content(linkedin: str, article: str) -> None:
    """Render LinkedIn post and Marketing Article from their dedicated JSON keys."""
    if linkedin:
        with st.container(border=True):
            st.markdown("**📱 LinkedIn Post**")
            st.caption("Optimised for LinkedIn feed — hook, short paragraphs, emoji bullets.")
            st.markdown("---")
            st.markdown(linkedin)

    if article:
        if linkedin:
            st.divider()
        with st.container(border=True):
            st.markdown("**📰 Marketing Article**")
            st.caption("Quick-read format — 'Why Now' angle for content marketing.")
            st.markdown("---")
            st.markdown(article)


def _render_how_it_works(body: str) -> None:
    import re as _re
    steps = _re.split(r"(?=\*\*Step \d)", body.strip())
    steps = [s.strip() for s in steps if s.strip()]
    for step in steps:
        m = _re.match(r"\*\*(.+?)\*\*[:\s]*([\s\S]*)", step)
        header = m.group(1).strip() if m else ""
        desc = m.group(2).strip() if m else step
        with st.container(border=True):
            st.markdown(f"**{header}**" if header else "")
            st.markdown(desc)
        st.markdown("")


def _render_objections(body: str) -> None:
    import re as _re
    pairs = _re.split(r"(?m)^---$", body)
    pairs = [p.strip() for p in pairs if p.strip()]
    for pair in pairs:
        halves = _re.split(r"(?=\*\*✅)", pair, maxsplit=1)
        concern = halves[0].strip()
        pivot = halves[1].strip() if len(halves) > 1 else ""
        col_l, col_r = st.columns([1, 1])
        with col_l:
            with st.container(border=True):
                st.markdown(concern)
        with col_r:
            with st.container(border=True):
                st.markdown(pivot)
        st.markdown("")


def _render_faq(body: str) -> None:
    import re as _re
    items = _re.split(r"(?=\*\*Q:)", body.strip())
    items = [i.strip() for i in items if i.strip()]
    for item in items:
        m = _re.match(r"\*\*Q:\s*(.+?)\*\*\s*([\s\S]*)", item)
        if m:
            question = m.group(1).strip()
            answer = m.group(2).strip()
            with st.expander(question):
                st.markdown(answer)
        else:
            st.markdown(item)


def _render_sales_battlecard(content: str) -> None:
    """Parse SALES_BATTLECARD sections and render with dedicated layouts."""
    import re as _re
    raw_sections = _re.split(r"(?=### )", content.strip())
    sections = [s.strip() for s in raw_sections if s.strip()]

    if not sections:
        st.info("No Sales content was generated.")
        return

    for idx, section in enumerate(sections):
        lines = section.split("\n", 1)
        header_line = lines[0].strip().lstrip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        if "How It Works" in header_line:
            st.markdown(f"### {header_line}")
            st.markdown("---")
            _render_how_it_works(body)
        elif "Objection" in header_line:
            st.markdown(f"### {header_line}")
            st.markdown("---")
            _render_objections(body)
        elif "FAQ" in header_line:
            st.markdown(f"### {header_line}")
            st.markdown("---")
            _render_faq(body)
        else:
            with st.container(border=True):
                st.markdown(f"### {header_line}")
                st.markdown("---")
                st.markdown(body)

        if idx < len(sections) - 1:
            st.divider()


def _render_gtm_suite(content: str) -> None:
    """Split EXTERNAL_GTM on '### ' markers and render each pillar."""
    import re as _re
    raw_sections = _re.split(r"(?=### )", content.strip())
    sections = [s.strip() for s in raw_sections if s.strip()]

    if not sections:
        st.info("No GTM content was generated.")
        return

    for idx, section in enumerate(sections):
        lines = section.split("\n", 1)
        header_line = lines[0].strip().lstrip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        pillar_name = next(
            (name for name in _GTM_PILLAR_CAPTIONS if name in header_line),
            header_line,
        )
        caption = _GTM_PILLAR_CAPTIONS.get(pillar_name, "")

        if "Market Education" in pillar_name:
            st.markdown(f"### {pillar_name}")
            if caption:
                st.caption(caption)
            _render_market_education(body)
        else:
            with st.container(border=True):
                st.markdown(f"### {pillar_name}")
                if caption:
                    st.caption(caption)
                st.markdown("---")
                st.markdown(body)

        if idx < len(sections) - 1:
            st.divider()


def _render_recruiting_suite(narratives: dict, persona: str) -> None:
    """Render the Recruiter's Playbook from 5 dedicated narrative keys."""
    import re as _re

    def _sections_from(key: str) -> list[tuple[str, str]]:
        """Split a narrative field on ### headers into (header, body) pairs."""
        raw = narratives.get(key, "")
        if not raw:
            return []
        parts = _re.split(r"(?=### )", raw.strip())
        result = []
        for part in parts:
            if not part.strip():
                continue
            lines = part.split("\n", 1)
            header = lines[0].strip().lstrip("# ").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            if header:
                result.append((header, body))
        return result

    # Tab assignments: each key maps to one or two ### sections
    outreach_sections  = _sections_from("OUTREACH_HOOK")   # Hook + Careers Blurb
    playbook_sections  = (
        _sections_from("COMPANY_PITCH") +                   # Company Pitch + Technical Why
        _sections_from("KEY_TALKING_POINTS")                # Talking Points
    )
    screening_sections = (
        _sections_from("ROLE_REQUIREMENTS") +               # Role Requirements
        _sections_from("SCREENING_GUIDE")                   # Screening Guide + Cheat Sheet
    )

    any_content = outreach_sections or playbook_sections or screening_sections
    if not any_content:
        st.info("No Recruiting content was generated.")
        return

    st.caption(f"Persona: **{persona}**")

    tab_outreach, tab_playbook, tab_screening = st.tabs([
        "📤 Outreach",
        "📖 The Playbook",
        "📋 Screening Guide",
    ])

    for tab_obj, sections in (
        (tab_outreach,  outreach_sections),
        (tab_playbook,  playbook_sections),
        (tab_screening, screening_sections),
    ):
        with tab_obj:
            if not sections:
                st.info("No content for this section.")
                continue
            for header, body in sections:
                with st.container(border=True):
                    st.markdown(f"### {header}")
                    st.markdown("---")
                    st.markdown(body)


def _render_tech_one_pager(content: str) -> None:
    """Render TECH_ONE_PAGER with a clean documentation-heavy layout."""
    import re as _re
    raw_sections = _re.split(r"(?=### )", content.strip())
    sections = [s.strip() for s in raw_sections if s.strip()]

    if not sections:
        st.info("No Technical One-Pager content was generated.")
        return

    for idx, section in enumerate(sections):
        lines = section.split("\n", 1)
        header_line = lines[0].strip().lstrip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        with st.container(border=True):
            st.markdown(f"### {header_line}")
            st.markdown("---")
            st.markdown(body)

        if idx < len(sections) - 1:
            st.markdown("")


def _render_customer_collateral(content: str) -> None:
    """Render CUSTOMER_COLLATERAL as a narrative business brief with a styled CTA."""
    if not content:
        st.info("No Customer Collateral content was generated.")
        return

    lines = content.split("\n")
    cta_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("**→")),
        None,
    )

    if cta_idx is not None:
        body = "\n".join(lines[:cta_idx]).strip()
        cta_raw = lines[cta_idx].strip().lstrip("*→ ").rstrip("*")
        st.markdown(body)
        st.markdown(
            f'<div class="hve-cta">→ {cta_raw}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(content)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="hve-header">
    <h1>⚡ Heron Velocity Engine</h1>
    <p>Intelligence Hub &nbsp;·&nbsp; Engineering Truth to Market Velocity</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Mission icons — shared between triage card and tabs
# ---------------------------------------------------------------------------

_MISSION_ICONS: dict[str, str] = {
    "GTM":                "🚀",
    "Sales":              "💰",
    "Recruiting":         "🤝",
    "Tech One-Pager":     "📄",
    "Customer Collateral": "🎯",
}

# ---------------------------------------------------------------------------
# Sidebar — Mission Control
# ---------------------------------------------------------------------------

# Safe defaults for variables defined inside the sidebar block.
user_input: str = ""
selected_missions: list[str] = []
generate_clicked: bool = False

with st.sidebar:
    st.markdown("### ⚡ Run Pipeline")
    st.markdown("---")

    user_input = st.text_area(
        "🔍  News / Technical Update",
        placeholder="Paste a spec excerpt, news item, or URL…",
        height=160,
    )

    # ── Intelligence Triage ────────────────────────────────────────────────
    if user_input.strip():
        triage_clicked = st.button(
            "🔍 Run Intelligence Triage",
            use_container_width=True,
            help="AI pre-scan evaluates this snippet against five mission criteria.",
        )
        if triage_clicked:
            with st.spinner("Triaging…"):
                triage: TriageResult = triage_news(user_input.strip())
            st.session_state["triage"] = triage
            # Pre-select recommended missions — user can still override below
            if triage.recommendations:
                st.session_state["mission_selection"] = list(triage.recommendations.keys())

    # Triage card — shown whenever results exist for the current input
    if st.session_state["triage"] is not None and user_input.strip():
        triage: TriageResult = st.session_state["triage"]
        with st.container(border=True):
            st.markdown("#### 🔍 Intelligence Triage")
            if triage.recommendations:
                for mission, rec in triage.recommendations.items():
                    icon = _MISSION_ICONS.get(mission, "•")
                    badge_class = {"P1": "hve-badge-p1", "P2": "hve-badge-p2", "P3": "hve-badge-p3"}.get(rec.priority, "hve-badge-p2")
                    badge_label = {"P1": "P1 Critical", "P2": "P2 Relevant", "P3": "P3 Info"}.get(rec.priority, rec.priority)
                    st.markdown(
                        f'{icon} **{mission}** &nbsp;<span class="hve-badge {badge_class}">{badge_label}</span>  \n'
                        f'> {rec.rationale}',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown("*No strong mission signal detected in this snippet.*")

    st.markdown("### 🎯 Mission Configuration")

    selected_missions = st.multiselect(
        "Select Output Missions",
        options=list(MISSION_TO_FIELD.keys()),
        key="mission_selection",
        help="Pre-checked by Intelligence Triage — override as needed.",
    )

    if "Recruiting" in selected_missions:
        st.selectbox(
            "Target Candidate Persona",
            options=list(TARGET_PERSONA_BRIEFS.keys()),
            key="target_persona",
            help="Tailors the Talent Acquisition Suite to the candidate's technical domain.",
        )

    st.markdown("---")
    generate_clicked = st.button(
        "Generate Velocity Pack", type="primary", use_container_width=True
    )

# ---------------------------------------------------------------------------
# Intelligence Executive Summary — main area (shown between triage and generate)
# ---------------------------------------------------------------------------

if st.session_state.get("triage") is not None and st.session_state.get("pack") is None:
    _triage_display: TriageResult = st.session_state["triage"]
    if _triage_display.recommendations:
        st.markdown("""
        <div class="hve-triage-banner">
            <p class="label">📋 Intelligence Executive Summary</p>
            <p class="sub">AI pre-scan complete — missions pre-selected by signal strength. Override in the sidebar before generating.</p>
        </div>""", unsafe_allow_html=True)

        _cols = st.columns(len(_triage_display.recommendations))
        for _col, (_mission, _rec) in zip(_cols, _triage_display.recommendations.items()):
            _icon = _MISSION_ICONS.get(_mission, "•")
            _badge_class = {"P1": "hve-badge-p1", "P2": "hve-badge-p2", "P3": "hve-badge-p3"}.get(_rec.priority, "hve-badge-p2")
            _badge_label = {"P1": "P1 Critical", "P2": "P2 Relevant", "P3": "P3 Info"}.get(_rec.priority, _rec.priority)
            with _col:
                with st.container(border=True):
                    st.markdown(
                        f'**{_icon} {_mission}**&nbsp;&nbsp;<span class="hve-badge {_badge_class}">{_badge_label}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(_rec.rationale)
                    if _rec.strategic_rationale:
                        st.markdown(
                            f'<p style="font-size:11px;color:#3D4A58;margin-top:4px;">'
                            f'<em>Strategic: {_rec.strategic_rationale}</em></p>',
                            unsafe_allow_html=True,
                        )

        st.markdown("")

# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

if generate_clicked:
    if not user_input.strip():
        st.error("Please enter a technical update or news item before generating.")
        st.stop()
    if not selected_missions:
        st.error("Please select at least one Output Mission.")
        st.stop()

    with st.status("HVE Orchestrator: Deploying Agents…", expanded=True) as _status:
        st.write("🔍 Librarian: Verifying Technical Specs…")
        st.write("🧠 Strategist: Synthesizing Narrative Missions…")
        try:
            pack: VelocityPack = run_velocity_pipeline(
                user_input=user_input.strip(),
                target_persona=st.session_state["target_persona"],
                selected_missions=selected_missions,
            )
        except Exception as exc:
            _status.update(label="Pipeline Error", state="error", expanded=True)
            st.error(f"Pipeline error: {exc}")
            st.stop()
        _status.update(label="Velocity Pack Ready ✓", state="complete", expanded=False)

    st.session_state["pack"] = pack
    st.session_state["selected_missions"] = selected_missions
    st.session_state.pop("triage", None)   # triage is for pre-selection only

# ---------------------------------------------------------------------------
# Intelligence Hub
# ---------------------------------------------------------------------------

if st.session_state["pack"] is not None:
    pack: VelocityPack = st.session_state["pack"]
    active_persona: str = st.session_state.get("target_persona", "Hardware/Power Electronics")
    active_missions: list[str] = st.session_state.get("selected_missions", list(MISSION_TO_FIELD.keys()))

    # -- Confidence Score Display ---------------------------------------------
    _conf = pack.confidence
    _conf_color = "#28A745" if _conf >= 80 else "#FFC107" if _conf >= 50 else "#DC3545"
    _conf_label = "High Confidence" if _conf >= 80 else "Medium Confidence" if _conf >= 50 else "Low Confidence — Review Required"
    _conf_delta = f"{_conf - 80:+d}% vs threshold" if _conf != 80 else "At threshold"

    with st.container(border=True):
        _mc1, _mc2 = st.columns([1, 3])
        with _mc1:
            st.metric(
                label="Grounding Score",
                value=f"{_conf}%",
                delta=_conf_delta,
                delta_color="normal" if _conf >= 80 else "inverse",
            )
            st.markdown(
                f'<p style="font-size:11px;color:{_conf_color};font-weight:600;margin-top:-8px;">{_conf_label}</p>',
                unsafe_allow_html=True,
            )
        with _mc2:
            st.caption("Grounded claims / total claims identified in input vs Heron SST-V2 spec")
            st.progress(_conf / 100)
            if _conf < 80:
                st.warning("⚠️ Verify all technical claims before external use.", icon=None)

    # -- Strategist Narrative Logic expander ----------------------------------
    with st.expander("🧠 Strategist Narrative Logic — First Principles", expanded=False):
        left, right = st.columns([1, 2])

        with left:
            st.markdown("**Run Parameters**")
            confidence_icon = (
                "🟢" if pack.confidence >= 80 else
                "🟡" if pack.confidence >= 60 else "🔴"
            )
            st.markdown(f"- **Missions:** {', '.join(active_missions)}")
            if "Recruiting" in active_missions:
                st.markdown(f"- **Candidate Persona:** {active_persona}")
            st.markdown(f"- **Grounding Score:** {confidence_icon} {pack.confidence} / 100")
            st.markdown(f"- **Blocks Generated:** {len(pack.narratives)}")

        with right:
            if "Recruiting" in active_missions and active_persona in _ROLE_LOGIC:
                st.markdown("**Persona Logic**")
                st.markdown(_ROLE_LOGIC.get(active_persona, ""))

    st.markdown("")

    # -- Output tabs ----------------------------------------------------------
    _ALL_TAB_META: dict[str, tuple[str, str, str | None]] = {
        "GTM":                ("🚀 GTM",               "GTM Multi-Pillar Suite",  None),
        "Sales":              ("💰 Sales",             "Sales Battlecard",        None),
        "Recruiting":         ("🤝 Recruiting",        "Talent Acquisition Suite", active_persona),
        "Tech One-Pager":     ("📄 Tech One-Pager",    "Technical One-Pager",     None),
        "Customer Collateral": ("🎯 Cust. Collateral", "Customer Collateral",     None),
    }

    # Only create a tab when the mission was requested AND its field key is present.
    # Recruiting is special: its sentinel key expands to 5 sub-fields, so check those.
    def _mission_has_content(m: str) -> bool:
        if m == "Recruiting":
            return any(pack.narratives.get(k) for k in RECRUITING_SUB_FIELDS)
        return bool(pack.narratives.get(MISSION_TO_FIELD.get(m, "")))

    available_tabs = [m for m in active_missions if _mission_has_content(m)]

    if not available_tabs:
        st.info("No mission output available. Please generate a Velocity Pack.")
    else:
        tab_labels = [_ALL_TAB_META.get(m, (m,))[0] for m in available_tabs]
        all_tabs = st.tabs(tab_labels)

        for tab_obj, mission in zip(all_tabs, available_tabs):
            # Mandate 2: .get() with a safe fallback tuple — no bracket access
            meta = _ALL_TAB_META.get(mission, (mission, mission, None))
            _icon_label, heading, role_label = meta
            field_key = MISSION_TO_FIELD.get(mission, "")
            content = pack.narratives.get(field_key, "")

            with tab_obj:
                try:
                    if mission == "GTM":
                        st.markdown(f"### {heading}")
                        st.markdown("---")
                        if content:
                            _render_gtm_suite(content)
                        else:
                            st.info("No GTM content was generated.")
                        # Social Blast — rendered from dedicated JSON keys
                        linkedin_content = pack.narratives.get("LINKEDIN_POST", "")
                        article_content = pack.narratives.get("MARKETING_ARTICLE", "")
                        if linkedin_content or article_content:
                            st.divider()
                            st.markdown("### 🚀 Social Blast")
                            st.caption("Ready-to-publish content — two dedicated formats.")
                            _render_social_content(linkedin_content, article_content)
                    elif mission == "Sales":
                        st.markdown(f"### {heading}")
                        st.markdown("---")
                        if content:
                            _render_sales_battlecard(content)
                        else:
                            st.info("No Sales content was generated.")
                    elif mission == "Tech One-Pager":
                        st.markdown(f"### {heading}")
                        st.markdown("---")
                        if content:
                            _render_tech_one_pager(content)
                        else:
                            st.info("No Technical One-Pager content was generated.")
                    elif mission == "Customer Collateral":
                        if content:
                            _render_customer_collateral(content)
                        else:
                            st.info("No Customer Collateral content was generated.")
                    elif mission == "Recruiting":
                        _render_recruiting_suite(pack.narratives, active_persona)
                    else:
                        with st.container(border=True):
                            st.markdown(f"### {heading}")
                            st.markdown("---")
                            if content:
                                st.markdown(content)
                            else:
                                st.info("No content generated for this mission.")
                except Exception as render_exc:
                    st.error(f"Could not render **{mission}** tab: {render_exc}")
