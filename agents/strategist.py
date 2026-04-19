"""
Strategist Agent — Heron Velocity Engine
Multi-persona architect. Builds prompts dynamically from a modular block-spec
registry so only selected missions are sent to the model.
"""

import json
import os
import re

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# ---------------------------------------------------------------------------
# Sub-role briefs
# ---------------------------------------------------------------------------

TARGET_PERSONA_BRIEFS: dict[str, str] = {
    "Hardware/Power Electronics": (
        "This candidate owns core conversion hardware: SiC device selection, magnetic design, "
        "and thermal management. Their world is constrained by physics at scale.\n"
        "Technical hooks:\n"
        "- SiC MOSFET selection and gate-drive optimization for 1.2kV and 3.3kV devices.\n"
        "- Magnetic design for MV isolation stages at 50-200kHz with minimized core loss.\n"
        "- Thermal stack: at 98.5pct efficiency and 4.2MW per unit, 63kW of heat must be managed — "
        "junction-to-ambient budget is the constraint everything else is subordinate to.\n"
        "- At 40GW, every design decision ships at scale — not a prototype.\n"
        "Motivations: depth of the physics problem, end-to-end hardware ownership, scale of impact.\n"
        "Avoid perks/culture language. Talk about the thermal budget and the SiC design problem."
    ),
    "Firmware/Software": (
        "This candidate builds software-defined power architecture and real-time control. "
        "Their world is deterministic execution under tight timing constraints.\n"
        "Technical hooks:\n"
        "- Software-defined switching: nanosecond gate-drive sequences at 1.2kV SiC — "
        "control loops where microseconds of jitter equal lost MW.\n"
        "- Deterministic RTOS design: scheduling, interrupt latency, hard real-time guarantees "
        "on embedded targets at 4.2MW.\n"
        "- HIL simulation and closed-loop verification before hardware touches a live grid.\n"
        "- At 40GW, a 1us dead-time optimization is a production yield gain across thousands of units.\n"
        "Motivations: hard latency-constrained problems, code that directly affects physical systems.\n"
        "Avoid Agile/sprint language. Use: control loop, RTOS, deterministic, embedded, interrupt."
    ),
    "Grid Integration/Utilities": (
        "This candidate owns bidirectional grid stability, harmonic compliance, and interconnection. "
        "Their world is IEEE standards and the physics of grid-forming behavior.\n"
        "Technical hooks:\n"
        "- Active harmonic filter algorithms holding THD below 3pct, satisfying IEEE 1547-2018 "
        "and UL 1741-SA.\n"
        "- Grid-forming sequencing: blackstart capability and frequency regulation that "
        "legacy inverters structurally cannot provide.\n"
        "- Bidirectional stability: clean import/export transitions without voltage transients.\n"
        "- At 40GW scale, Heron's compliance posture defines what gets connected to the grid.\n"
        "Motivations: writing the compliance standard others must meet, grid stability at scale.\n"
        "Use: THD, grid-forming, IEEE 1547, PCC, droop control, blackstart. No sales language."
    ),
    "Supply Chain/Operations": (
        "This candidate owns procurement strategy, supplier development, and manufacturing ramp. "
        "Their world is lead times, yield rates, and BoM optimization at infrastructure scale.\n"
        "Technical hooks:\n"
        "- SiC module supply chain: qualifying second sources for 1.2kV and 3.3kV devices "
        "at a time when global SiC capacity is constrained.\n"
        "- 40GW manufacturing mandate: building operational infrastructure at a scale that "
        "power electronics has never attempted.\n"
        "- Legacy elimination by design: every transformer Heron replaces is a supplier "
        "relationship that doesn't need to exist — BoM simplification as architecture.\n"
        "- Lead time arbitrage: Heron's 12-week deployment vs. 18-36 month legacy procurement "
        "is a supply chain problem as much as a product problem.\n"
        "Motivations: building supply chains for genuinely new technology at infrastructure scale.\n"
        "Use: BoM, SiC supply, yield, NPI, lead time. Avoid generic ops language."
    ),
}

# Backward-compat alias — orchestrator and UI import this name
SUB_ROLE_BRIEFS = TARGET_PERSONA_BRIEFS

DEFAULT_PERSONA = "Hardware/Power Electronics"
DEFAULT_SUB_ROLE = DEFAULT_PERSONA  # alias

# ---------------------------------------------------------------------------
# Mission → field mapping (used by orchestrator and UI)
# ---------------------------------------------------------------------------

MISSION_TO_FIELD: dict[str, str] = {
    "GTM":                "EXTERNAL_GTM",
    "Sales":              "SALES_BATTLECARD",
    "Recruiting":         "RECRUITING_HOOK",
    "Tech One-Pager":     "TECH_ONE_PAGER",
    "Customer Collateral": "CUSTOMER_COLLATERAL",
}

# Fields generated regardless of mission selection
ALWAYS_FIELDS: list[str] = ["VISUAL_DIRECTIVES", "TECHNICAL_SCHEMATIC"]

ALL_FIELDS: list[str] = [
    "EXTERNAL_GTM",
    "LINKEDIN_POST",
    "MARKETING_ARTICLE",
    "SALES_BATTLECARD",
    "OUTREACH_HOOK",
    "COMPANY_PITCH",
    "ROLE_REQUIREMENTS",
    "SCREENING_GUIDE",
    "KEY_TALKING_POINTS",
    "TECH_ONE_PAGER",
    "CUSTOMER_COLLATERAL",
    "VISUAL_DIRECTIVES",
    "TECHNICAL_SCHEMATIC",
]

# The 5 sub-keys that together constitute the Recruiting mission
RECRUITING_SUB_FIELDS: list[str] = [
    "OUTREACH_HOOK",
    "COMPANY_PITCH",
    "ROLE_REQUIREMENTS",
    "SCREENING_GUIDE",
    "KEY_TALKING_POINTS",
]

FIELD_DISPLAY_NAMES: dict[str, str] = {
    "EXTERNAL_GTM":        "GTM Suite (Campaign + Education)",
    "LINKEDIN_POST":       "LinkedIn Post",
    "MARKETING_ARTICLE":   "Marketing Article",
    "SALES_BATTLECARD":    "Sales Battlecard",
    "OUTREACH_HOOK":       "Outreach Hook",
    "COMPANY_PITCH":       "Company Pitch",
    "ROLE_REQUIREMENTS":   "Role Requirements",
    "SCREENING_GUIDE":     "Screening Guide",
    "KEY_TALKING_POINTS":  "Key Talking Points",
    "TECH_ONE_PAGER":      "Technical One-Pager",
    "CUSTOMER_COLLATERAL": "Customer Collateral",
    "VISUAL_DIRECTIVES":   "Visual Directives",
    "TECHNICAL_SCHEMATIC": "Technical Schematic (Mermaid)",
}

LOW_SCORE_THRESHOLD = 70

_DISCLAIMER = (
    "\n\n> WARNING: Librarian confidence is below threshold. "
    "Verify all technical claims against the SST-V2 specification before external use."
)

# ---------------------------------------------------------------------------
# Modular block specs — one entry per output field
# ---------------------------------------------------------------------------

_BLOCK_SPECS: dict[str, str] = {

    "EXTERNAL_GTM": (
        "EXTERNAL_GTM: GTM Suite — three distinct deliverables in one block.\n\n"
        "VOICE MANDATE: Tesla Mafia — engineering-first, first-principles, no hedging.\n"
        "Focus on the Physics Bottleneck of the grid. Every sentence must contain a fact or a frame.\n"
        "Banned: revolutionary, game-changing, cutting-edge, innovative, seamless, robust.\n\n"
        "Output EXACTLY these three section headers (emoji + text, as written). No preamble.\n\n"

        "### 🎯 Campaign Launcher\n"
        "Channel strategy + hero copy for this GTM push. Write these five labelled items "
        "with a blank line between each:\n\n"
        "**Primary Channel:** [Exactly one recommendation with a one-sentence justification: "
        "'LinkedIn — Professional Trust' for enterprise buyers and Data Center Architects, OR "
        "'X/Twitter — Technical Reach' for engineers and tech-savvy founders. "
        "State why this channel fits the target segment.]\n\n"
        "**Killer Visual Concept:** [1 sentence. Describe the ideal hero image — what it physically "
        "shows (e.g., a side-by-side electrical room before/after), what quantified data point it "
        "anchors to, and the emotional register it hits. No stock photo clichés.]\n\n"
        "**Headline:** [Max 6 words. A hard engineering claim as fact — "
        "e.g. 'The 12-Week Grid.' or '800V DC. No Transformer.']\n\n"
        "**Sub-headline:** [1 sentence, max 20 words. Names the specific physics constraint "
        "being broken and the Heron mechanism that breaks it.]\n\n"
        "**CTA:** [3-5 words, action-oriented — e.g. 'See the Architecture']\n\n"

        "### 📜 Technical One-Pager\n"
        "Four 'Hard Truths' bullets for partner and investor briefings. Zero softening language.\n"
        "Each bullet must be: **[Spec Name]:** [hard number or binary fact — no ranges].\n"
        "Cover: peak efficiency %, electrical-room footprint reduction %, "
        "legacy stages eliminated (name each one), Time-to-Power lead-time delta in weeks.\n\n"

        "### 💡 Market Education\n"
        "Side-by-side comparison. Use EXACTLY these two sub-headers and bullet format. "
        "Feature names in both sections MUST be identical so they align line-by-line:\n\n"
        "**Legacy Architecture**\n"
        "- Footprint: [value]\n"
        "- Procurement Lead Time: [value]\n"
        "- Peak Efficiency: [value]\n"
        "- Grid-Forming: [value]\n"
        "- Stages in Power Chain: [list]\n\n"
        "**Heron Architecture**\n"
        "- Footprint: [value — must reflect 65% reduction]\n"
        "- Procurement Lead Time: [value]\n"
        "- Peak Efficiency: [value]\n"
        "- Grid-Forming: [value]\n"
        "- Stages in Power Chain: [list]\n\n"
        "[1-2 sentences: anchor the 65% footprint reduction and supply-chain speed as "
        "compounding NPV gains over a 20-year asset life.]"
    ),

    "SALES_BATTLECARD": (
        "SALES_BATTLECARD: Sales enablement brief for a live deal.\n"
        "VOICE: Confident Insider — technically authoritative but focused on solving the "
        "customer's business problems (Time-to-Power and Opex). No softening language. "
        "No superlatives. Every claim traces to a number or mechanism.\n\n"
        "Output EXACTLY these three section headers (emoji + text, as written). No preamble.\n\n"

        "### ⚙️ How It Works\n"
        "3-step technical walkthrough. One blank line between steps.\n\n"
        "**Step 1 — Direct MV Input:** [2-3 sentences. What the system accepts, at what "
        "voltage, from what source. Name the grid connection spec and eliminate the first "
        "legacy stage.]\n\n"
        "**Step 2 — SiC High-Frequency Conversion:** [2-3 sentences. What happens inside "
        "the unit. Name the switching frequency range, SiC device class (1.2kV or 3.3kV), "
        "and the peak efficiency result.]\n\n"
        "**Step 3 — Software-Defined 800V Output:** [2-3 sentences. What is delivered to "
        "the rack or grid. Name the output spec, every legacy stage eliminated, and the "
        "Time-to-Power delta in weeks vs. legacy procurement.]\n\n"

        "### 🛡️ Objection Handler\n"
        "3 objection pairs. Separate each pair with a line containing only: ---\n"
        "Write each pair in this exact format (blank line between Concern and Pivot):\n\n"
        "**🔴 Customer Concern:** [the concern a buyer raises about procurement lead times]\n\n"
        "**✅ The Heron Pivot:** [2-3 sentences. Cite the specific lead-time delta: SiC "
        "module procurement vs. electrical-steel transformer procurement in weeks.]\n\n"
        "---\n\n"
        "**🔴 Customer Concern:** [the concern about reliability, redundancy, or ride-through]\n\n"
        "**✅ The Heron Pivot:** [2-3 sentences. Cite SuperBBU 30-second ride-through, "
        "modular hot-swap redundancy, or uptime spec vs. traditional UPS.]\n\n"
        "---\n\n"
        "**🔴 Customer Concern:** [the concern about electrical room footprint or integration cost]\n\n"
        "**✅ The Heron Pivot:** [2-3 sentences. Cite 65% footprint reduction and translate "
        "it to business value: $/sqft saved, compute density gained, or construction cost avoided.]\n\n"

        "### ❓ FAQ\n"
        "4-5 high-value questions a CFO, CTO, or procurement lead would ask. "
        "Every answer must contain a number or mechanism. Format:\n\n"
        "**Q: [question]**\n"
        "[2-3 sentence answer.]\n\n"
        "Topics: interconnection voltage, warranty terms, SiC lifetime/MTBF, upgrade path, "
        "comparison to legacy UPS architecture, or payback period.\n"
        "Rules: no vague answers. No ranges. If estimated, say so."
    ),

    # --- Recruiting sub-fields (5 independent JSON keys) -------------------

    "OUTREACH_HOOK": (
        "OUTREACH_HOOK: Two recruiting artifacts for direct outreach — tailored to TARGET CANDIDATE PERSONA.\n"
        "VOICE: Elite and high-growth. Insider knowledge, not corporate speak. "
        "Banned: 'passionate', 'collaborative', 'dynamic', 'fast-paced', 'exciting opportunity'.\n"
        "Draw ALL technical language from PERSONA BRIEF. Draw market context from TECHNICAL CONTEXT.\n\n"

        "### ⚡ The Outreach Hook\n"
        "A LinkedIn DM or cold email to a senior engineer. Three short paragraphs.\n"
        "Paragraph 1 — Hook: One hard technical fact from TECHNICAL CONTEXT that directly "
        "intersects this persona's domain. Specific enough that it feels personal, not templated.\n"
        "Paragraph 2 — The Problem: Name the specific constraint from PERSONA BRIEF they would "
        "own at Heron. Describe the physics or systems problem in the persona's technical vocabulary "
        "— no job-description language.\n"
        "Paragraph 3 — CTA: Short and direct. Easy to say yes to. "
        "'Worth a 20-minute call?' No salary. No benefits.\n\n"

        "### 🚀 Careers Page Blurb\n"
        "60-90 words for a careers page or LinkedIn job post.\n"
        "Lead with the technical problem the role solves. Name the specific domain from "
        "PERSONA BRIEF. One hard number (40GW, $140M, 98.5pct efficiency, 63kW thermal budget). "
        "Direct CTA. No buzzwords. No benefits. No emojis."
    ),

    "COMPANY_PITCH": (
        "COMPANY_PITCH: Two sections telling the Heron story to top-tier talent — tailored to TARGET CANDIDATE PERSONA.\n"
        "VOICE: Bold and visionary, never vague. SpaceX-era confidence. No hedge words.\n"
        "Draw ALL technical language from PERSONA BRIEF. Draw market context from TECHNICAL CONTEXT.\n\n"

        "### 🏢 Company Pitch\n"
        "Two paragraphs.\n"
        "Paragraph 1 — The Problem at Scale: The 40GW power bottleneck. "
        "Name the specific grid crisis: AI data center demand for 800V DC at scale, "
        "grid interconnection queues, 18-36 month transformer lead times. "
        "Make this feel inevitable and urgent — a structural constraint that has to break.\n"
        "Paragraph 2 — Why Heron Wins: $140M Series B, SiC architecture eliminating the "
        "transformer-UPS-switchgear stack, direct MV-to-800V-DC at 98.5pct efficiency. "
        "One hard technical claim from TECHNICAL CONTEXT. No fundraising language.\n\n"

        "### 🏗️ Technical 'Why Heron'\n"
        "First-principles briefing for a skeptical senior engineer who has heard pitches before.\n"
        "Cover: (1) What Heron is building — direct MV-to-800V-DC, SiC architecture, 40GW mandate. "
        "(2) Why this persona's specific domain is load-bearing at scale — use exact terms from "
        "PERSONA BRIEF. (3) What legacy approaches structurally cannot do and why Heron's "
        "architecture requires solving this from first principles.\n"
        "3-4 technical paragraphs. No marketing language. Engineering briefing, not pitch."
    ),

    "ROLE_REQUIREMENTS": (
        "ROLE_REQUIREMENTS: Specific technical hiring bar for TARGET CANDIDATE PERSONA.\n"
        "Draw ALL requirements from PERSONA BRIEF and TECHNICAL CONTEXT. No soft skills. No 'nice to haves'.\n\n"

        "### ✅ Role Requirements\n"
        "3-4 specific requirements.\n"
        "Format: **[Requirement]:** [one sentence on why this capability is load-bearing at Heron at 40GW scale.]\n"
        "Examples: SiC thermal management for Hardware, deterministic RTOS for Firmware, "
        "IEEE 1547-2018 compliance for Grid Integration, SiC supply qualification for Supply Chain.\n"
        "Tie at least one requirement to a specific fact from TECHNICAL CONTEXT."
    ),

    "SCREENING_GUIDE": (
        "SCREENING_GUIDE: Tools for the hiring team to evaluate TARGET CANDIDATE PERSONA candidates.\n"
        "Draw ALL technical language from PERSONA BRIEF. Draw context from TECHNICAL CONTEXT.\n\n"

        "### 📋 Screening Guide\n"
        "3 key areas for the recruiter to assess in the initial 30-minute screen. "
        "Not a question list — a guide to what signal to listen for.\n"
        "Format: **[Area]:** [What to listen for — the specific signal that separates a great "
        "candidate from a good one in this persona's domain.]\n"
        "Area 1: Technical depth in the persona's core constraint (from PERSONA BRIEF). "
        "Area 2: Scale readiness — prototype mentality vs. production ownership. "
        "Area 3: Problem ownership — do they describe systems problems or just implementations?\n\n"

        "### 🤝 Interviewer Cheat Sheet\n"
        "For the hiring manager. Two labelled sections:\n\n"
        "**Questions to Ask:**\n"
        "2-3 technical questions specific to this persona's domain. "
        "Format: **Q:** [question]\n"
        "Probe for depth: thermal budget reasoning for Hardware, interrupt latency tradeoffs "
        "for Firmware, grid-forming sequencing for Grid Integration, SiC supplier qualification "
        "for Supply Chain.\n\n"
        "**Value Props to Close:**\n"
        "3 bullets. What to say when the candidate pushes back. "
        "Each: one concrete Heron differentiator and why it beats their current role."
    ),

    "KEY_TALKING_POINTS": (
        "KEY_TALKING_POINTS: Insider Q&A for the recruiting team — tailored to TARGET CANDIDATE PERSONA.\n"
        "These should feel like the Product team briefed the recruiter before a push — insider context, not spin.\n"
        "Draw ALL technical language from PERSONA BRIEF. Cite numbers from TECHNICAL CONTEXT.\n\n"

        "### 💬 Key Talking Points\n"
        "3-4 points for when candidates ask hard questions.\n"
        "Format: **Q:** [Common candidate question or hesitation]\n"
        "**A:** [2-3 sentence answer. Cite a specific number or fact from TECHNICAL CONTEXT. "
        "Re-frame the concern without dismissing it.]\n\n"
        "Must cover: (1) Why join now vs. waiting for Series C. "
        "(2) Heron's technical moat vs. ABB/Eaton/Schneider. "
        "(3) What the recent spec or market signal means for this role's roadmap. "
        "(4) Scale of the problem — what 40GW means in concrete terms for this persona."
    ),

    "LINKEDIN_POST": (
        "LINKEDIN_POST: Optimised LinkedIn feed post. Hook-heavy with hard line breaks.\n\n"
        "CRITICAL: This field contains ONLY the LinkedIn post. "
        "Do NOT include any article title, prose paragraphs from the marketing article, "
        "or any content that belongs in MARKETING_ARTICLE.\n\n"
        "Structure (use \\n\\n between every block):\n"
        "Line 1: A single counterintuitive claim or hard number, max 12 words. "
        "Stand-alone. Make the reader stop scrolling.\n\n"
        "Body: 2-3 short paragraphs of 1-2 sentences each. "
        "Separated by blank lines. Focus on Active-Isolation: name the components "
        "eliminated and why that matters to this segment.\n\n"
        "Mid-section: 3-5 bullet points, one per line, with a relevant emoji per bullet "
        "(e.g. ⚡ 🔋 📐 ⏱️ 📉).\n\n"
        "Close: one direct question or CTA sentence.\n\n"
        "Footer: #PowerElectronics #SiC #800VDC and 3 contextually relevant hashtags.\n\n"
        "Rules: every paragraph block separated by a blank line. "
        "No article titles. No prose longer than 2 sentences per paragraph."
    ),

    "MARKETING_ARTICLE": (
        "MARKETING_ARTICLE: Quick-read marketing article with a 'Why Now' angle.\n\n"
        "CRITICAL: This field contains ONLY the marketing article. "
        "Do NOT include any LinkedIn post hook, bullet emojis, or hashtags.\n\n"
        "Structure:\n"
        "# [Compelling article title — 'Why Now' angle, on its own line as an H1]\n\n"
        "[Paragraph 1 — Market Forcing Function: grid queue crisis, AI power demand, "
        "or regulation deadline. Max 60 words.]\n\n"
        "[Paragraph 2 — Heron Mechanism: what Heron does and what it eliminates. "
        "Name the specific stages removed. Max 60 words.]\n\n"
        "[Paragraph 3 — Business Case: NPV delta, speed-to-power, compliance unlock. Max 60 words.]\n\n"
        "Rules: Start with '# ' H1 title on its own line. "
        "No bullet points. Prose only. Exactly three paragraphs. "
        "Each paragraph separated by a blank line. Each paragraph max 60 words."
    ),

    "TECH_ONE_PAGER": (
        "TECH_ONE_PAGER: Structured technical document for partner and investor briefings.\n"
        "VOICE MANDATE: Engineering-precise, spec-driven, zero hedging. "
        "Every claim must trace to a number. No softening language.\n\n"
        "Output EXACTLY these five section headers (emoji + text, as written). No preamble.\n\n"

        "### 🏗️ Executive Technical Brief\n"
        "[2-3 sentences. What the system is, what it replaces, and the top-line performance "
        "claim. Include: 34.5kV AC to 800V DC, 4.2MW per unit, 98.5% peak efficiency, "
        "and the specific legacy stages eliminated.]\n\n"

        "### 📊 Verified Performance Specs\n"
        "Markdown table with EXACTLY these columns (pipe-delimited): Parameter | Value | Notes\n"
        "Include rows for: Peak Efficiency, Power Density, Input Voltage, Output Voltage, "
        "Ride-Through, Footprint Reduction, Legacy Stages Eliminated.\n"
        "All values must be hard numbers — no ranges, no vague qualifiers.\n\n"

        "### 🔌 Integration & Topology\n"
        "[Bulleted list. Cover: Active-Isolation architecture, direct MV grid interface, "
        "800V DC bus delivery to the rack, software-defined switching logic, "
        "and IEEE 1547-2018 grid-forming capability. One fact per bullet.]\n\n"

        "### 📏 Physical & Thermal Envelope\n"
        "[3-4 bullets. Cover: physical form factor, rack-unit footprint, "
        "heat dissipation at full load (derive from 4.2MW × (1 − 0.985) ≈ 63kW), "
        "and cooling method. Hard numbers only.]\n\n"

        "### ✅ Standards Compliance\n"
        "[Bulleted list. One bullet per standard. Include: IEEE 1547-2018 (grid-forming), "
        "UL 1741-SA (advanced inverter functions), and any applicable IEC or NEC references. "
        "One sentence per bullet explaining relevance to Heron's architecture.]\n"
        "Rules: no PR language. This document will be reviewed by engineers."
    ),

    "CUSTOMER_COLLATERAL": (
        "CUSTOMER_COLLATERAL: Narrative Business Brief — a flowing executive document.\n"
        "VOICE: Business outcome-first, narrative prose. No bullet lists. No section boxes.\n"
        "Every technical claim connects to dollars, time, or competitive risk.\n"
        "Banned: revolutionary, game-changing, cutting-edge, innovative, seamless, robust.\n\n"
        "Output exactly this structure. No preamble. No markdown headers except the H1 title.\n\n"

        "# [Compelling article-style headline — names the problem and the outcome, max 12 words]\n\n"

        "[Narrative Hook — Paragraph 1: 3-4 sentences. The market crisis right now. "
        "Name the specific bottleneck with a hard number: 18-36 month transformer lead times, "
        "AI cluster power demand at 800V DC, or grid interconnection queue delays. "
        "State the direct financial consequence for this buyer. Do not soften it.]\n\n"

        "[Narrative Hook — Paragraph 2: 3-4 sentences. Heron as the structural answer. "
        "Name what the system does (direct MV-to-800V-DC, SiC architecture, stage elimination). "
        "Connect the technical mechanism to the business outcome the buyer actually cares about. "
        "One hard number that proves the claim.]\n\n"

        "**💰 The Economic Case**\n"
        "[2-3 sentences of flowing prose. Efficiency delta as operating cost savings per year. "
        "Footprint reduction as $/sqft recovered or additional compute density. "
        "Supply-chain speed as the CapEx timing advantage in months.]\n\n"

        "**⚖️ What Legacy Cannot Do**\n"
        "[2-3 sentences of flowing prose. Not a comparison table — a business narrative. "
        "What is the buyer locked out of with legacy: stranded procurement cycles, "
        "compliance failure (IEEE 1547-2018), or inability to deliver 800V DC to the rack. "
        "Name the specific outcome Heron enables that ABB, Eaton, or Schneider structurally cannot.]\n\n"

        "**📈 Time Is the Variable**\n"
        "[2-3 sentences of flowing prose. Legacy procurement timeline vs. Heron. "
        "Express the delta as weeks saved. Translate that delta to a business value: "
        "earlier revenue recognition, lower interest carry on CapEx, or faster depreciation.]\n\n"

        "**The Cost of Waiting**\n"
        "[2-3 sentences. Strong closing argument. Every month of delay is quantifiable — "
        "name the monthly cost: interest carry, lost revenue per rack, or competitor advantage. "
        "Make the status quo feel financially irresponsible, not just inconvenient.]\n\n"

        "**→ [One-sentence CTA: specific, time-bound, named next action — "
        "e.g. 'Schedule a 30-minute architecture review this week.' or "
        "'Request the deployment timeline comparison for your project.']**\n\n"
        "Rules: prose only throughout. Every paragraph separated by a blank line. "
        "Every claim traces to a number. This will be read by a CFO or VP of Engineering."
    ),

    "VISUAL_DIRECTIVES": (
        "VISUAL_DIRECTIVES: Spec for one diagram.\n"
        "### Diagram: [title]\n"
        "**Type:** [type]\n"
        "**Hero Number:** [key metric]\n"
        "**Axes/Nodes:** [labels with units]\n"
        "**Comparison Baseline:** [legacy stack]\n"
        "**Key Annotation:** [insight viewer must leave with]\n"
        "Rules: one diagram only."
    ),

    "TECHNICAL_SCHEMATIC": (
        "TECHNICAL_SCHEMATIC: Raw Mermaid.js graph string. Keep it extremely simple.\n"
        "STRICT RULES:\n"
        "1. Start with exactly 'graph LR;' (with semicolon).\n"
        "2. Node IDs and labels use ONLY letters, numbers, spaces. "
        "No % / ( ) < > & ' symbols anywhere.\n"
        "3. Simple short labels only: A[Grid] or A[Heron Link]. "
        "Replace percent with pct, slash with and.\n"
        "4. Use --> for flow, -.-> for eliminated legacy stages.\n"
        "5. Data Center example:\n"
        "graph LR;\n"
        "    A[Grid 34kV] --> B[Heron Link]\n"
        "    B --> C[800V DC Bus]\n"
        "    C --> D[AI Rack]\n"
        "    B -.-> E[Old Transformer REMOVED]\n"
        "    B -.-> F[Old UPS REMOVED]\n"
        "6. Solar example:\n"
        "graph LR;\n"
        "    A[Solar Array] --> B[Heron SiC]\n"
        "    B <--> C[Battery Store]\n"
        "    B --> D[Grid Export]\n"
        "Output only the raw graph string. No fences, no explanation."
    ),
}

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_PROMPT_INTRO = (
    "You are the Heron Power Strategist. Return a single valid JSON object. "
    "No prose before or after the JSON. Each value is a Markdown-formatted string "
    "using \\n for newlines. Do NOT use triple backticks inside any string value.\n\n"
    "VOICE RULES (apply to all fields):\n"
    "- Banned words: revolutionary, game-changing, cutting-edge, innovative, "
    "world-class, seamless, robust, transformative.\n"
    "- Every claim must trace to a number or mechanism from the technical context.\n"
    "- Heron context: 40GW scale, SiC architecture, $140M Series B, "
    "direct MV-to-800V-DC eliminating transformer/UPS/switchgear.\n"
    "- Voice: Drew Baglino — first-principles, precise, no unnecessary complexity.\n"
    "- Use Markdown (### headers, **bold**, bullet lists) inside string values.\n"
)


def _build_system_prompt(selected_fields: list[str]) -> str:
    block_text = "\n\n--- FIELD SPECIFICATIONS ---\n\n" + "\n\n".join(
        _BLOCK_SPECS[f] for f in selected_fields if f in _BLOCK_SPECS
    )
    field_list = ", ".join(selected_fields)
    example_pairs = ", ".join(f'"{f}": "..."' for f in selected_fields)
    format_line = (
        f"\n\n--- OUTPUT FORMAT ---\n"
        f"Return a JSON object with exactly these keys: {field_list}\n"
        f"Example structure: " + "{" + example_pairs + "}"
    )
    raw = _PROMPT_INTRO + block_text + format_line
    # The system prompt contains no LangChain template variables — every { and }
    # is a literal character. Escape them so str.format_map() never misreads them.
    return raw.replace("{", "{{").replace("}", "}}")


HUMAN_PROMPT = """\
TECHNICAL CONTEXT:
{technical_context}

TARGET CANDIDATE PERSONA: {target_persona_label}
PERSONA BRIEF:
{target_persona_brief}\
"""

# ---------------------------------------------------------------------------
# Parser — JSON mode with preamble-robust extraction
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json|mermaid)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _error_blocks(message: str, fields: list[str]) -> dict[str, str]:
    return {f: f"[{message}]" for f in fields}


def _parse_json_response(raw: str | None, expected_fields: list[str]) -> dict[str, str]:
    """
    Extract JSON from LLM response with maximum resilience.

    Strategy:
    1. Guard against None / empty input.
    2. Strip markdown fences, try json.loads on the full string.
    3. If that fails, slice from first '{' to last '}' and retry.
    4. Normalize all returned keys to UPPER_CASE so casing variations
       from the LLM (e.g. 'recruiting_hook') are matched correctly.
    5. On total failure return per-field error strings — never raises.
    """
    if not raw:
        return _error_blocks("Error parsing narrative — empty response", expected_fields)

    try:
        cleaned = _strip_fences(raw)

        # Pass 1 — direct parse
        try:
            data: dict = json.loads(cleaned)
        except json.JSONDecodeError:
            # Pass 2 — brace-slice fallback
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end > start:
                data = json.loads(cleaned[start : end + 1])
            else:
                return _error_blocks("Error parsing narrative — no JSON found", expected_fields)

        # Normalise keys to uppercase so LLM casing variations never cause KeyErrors
        data = {k.upper(): v for k, v in data.items() if isinstance(k, str)}

        blocks: dict[str, str] = {}
        for f in expected_fields:
            value = data.get(f, "")
            if isinstance(value, str) and value.strip():
                blocks[f] = value.strip()
            else:
                blocks[f] = f"[{f} not returned by model]"

        if "TECHNICAL_SCHEMATIC" in blocks:
            blocks["TECHNICAL_SCHEMATIC"] = _strip_fences(blocks["TECHNICAL_SCHEMATIC"])

        return blocks

    except Exception as exc:
        return _error_blocks(f"Error parsing narrative — {exc}", expected_fields)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_market_narrative(
    technical_context: str,
    librarian_score: int | None = None,
    target_persona: str | None = None,
    selected_fields: list[str] | None = None,
) -> dict[str, str]:
    """
    Generate persona outputs for the requested fields from one technical brief.

    Returns a dict that ALWAYS contains every key in ALL_FIELDS. Keys for
    missions that were not requested are returned as empty strings.

    Raises:
        ValueError: If target_persona is not recognised.
    """
    # ── Mandate 1: initialise ALL keys to "" at the very start ──────────────
    # No matter what happens below, the returned dict will have every key.
    narratives: dict[str, str] = {k: "" for k in ALL_FIELDS}

    resolved_persona = target_persona or DEFAULT_PERSONA
    if resolved_persona not in TARGET_PERSONA_BRIEFS:
        valid = ", ".join(f'"{p}"' for p in TARGET_PERSONA_BRIEFS)
        raise ValueError(f"Unknown target_persona '{resolved_persona}'. Valid options: {valid}")

    # Determine which fields to request from the LLM.
    # EXTERNAL_GTM expansion: also pull social keys as dedicated JSON entries.
    # RECRUITING_HOOK expansion: the sentinel key expands to 5 focused sub-fields.
    if selected_fields:
        _extra: list[str] = []
        if "EXTERNAL_GTM" in selected_fields:
            for _sk in ("LINKEDIN_POST", "MARKETING_ARTICLE"):
                if _sk not in selected_fields:
                    _extra.append(_sk)
        # Expand the RECRUITING_HOOK sentinel to its 5 independent sub-fields
        _expanded = []
        for _f in selected_fields:
            if _f == "RECRUITING_HOOK":
                _expanded.extend(RECRUITING_SUB_FIELDS)
            else:
                _expanded.append(_f)
        fields_to_generate = list(dict.fromkeys(
            _expanded + _extra + [f for f in ALWAYS_FIELDS if f not in _expanded + _extra]
        ))
    else:
        fields_to_generate = ALL_FIELDS

    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            model_kwargs={"response_format": {"type": "json_object"}},
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", _build_system_prompt(fields_to_generate)),
            ("human", HUMAN_PROMPT),
        ])

        llm_result = (prompt | llm).invoke({
            "technical_context": technical_context,
            "target_persona_label": resolved_persona,
            "target_persona_brief": TARGET_PERSONA_BRIEFS.get(resolved_persona, ""),
        })

        raw_content: str | None = getattr(llm_result, "content", None)
        parsed = _parse_json_response(raw_content, fields_to_generate)

        # Merge parsed blocks into the pre-initialised narratives dict.
        # Only overwrite keys that have real content (non-empty, non-error strings).
        for key, value in parsed.items():
            if value and not value.startswith("["):
                narratives[key] = value

    except Exception:
        # LLM call failed — return the pre-initialised dict with empty strings.
        pass

    if librarian_score is not None and librarian_score < LOW_SCORE_THRESHOLD:
        narratives = {k: v + _DISCLAIMER if v else v for k, v in narratives.items()}

    return narratives


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    SAMPLE_CONTEXT = """\
- Input/Output: 34.5kV AC (Utility Grid) to 800V DC (Rack-Ready).
- Power Density: 4.2MW per unit.
- Peak Efficiency: 98.5pct (MV-to-Rack).
- Footprint Impact: 70pct reduction in electrical room space.
- Legacy Elimination: Replaces LV Transformers, MSBs, UPS, PDUs, RPPs.
- Ride-Through: SuperBBU provides 30-second ride-through.
- Grid-Forming: Active voltage/frequency regulation, blackstart capability.\
"""

    sep = "=" * 72

    print(f"\n{sep}\nFULL PACK TEST\n{sep}")
    blocks = get_market_narrative(SAMPLE_CONTEXT, librarian_score=85)
    for f, content in blocks.items():
        print(f"\n--- {FIELD_DISPLAY_NAMES.get(f, f)} ---\n{content[:300]}")

    print(f"\n{sep}\nSELECTED MISSIONS: Sales + Tech One-Pager\n{sep}")
    selective = get_market_narrative(
        SAMPLE_CONTEXT,
        selected_fields=["SALES_BATTLECARD", "TECH_ONE_PAGER"],
        target_persona="Grid Integration/Utilities",
    )
    for f, content in selective.items():
        print(f"\n--- {FIELD_DISPLAY_NAMES.get(f, f)} ---\n{content[:300]}")
