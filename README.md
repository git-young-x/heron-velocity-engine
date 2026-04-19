<img width="1325" height="754" alt="{031D9DC0-6291-41B7-9E62-F631133CC15E}" src="https://github.com/user-attachments/assets/76c3f9a7-8d66-4908-bbfd-b2c6f30f05ca" /># Heron Velocity Engine (HVE) 🚀
**Multi-Agent Strategic Intelligence Architecture for Rapid, Grounded Content Production.**

The **Heron Velocity Engine** is a prototype AI system designed to solve the "technical translation bottleneck." It takes high-signal market inputs (release notes, technical whitepapers, competitor intel) and automatically refracts them into verified, persona-specific mission packs for GTM, Sales, Engineering, and Recruiting teams.

---

## 🏗️ Architecture
https://v0.app/chat/heron-velocity-engine-sq9FQdd8oMw?ref=GZVFVC 

### The Core Intelligence Layer
HVE utilizes a multi-agent "Triage & Refract" workflow to ensure output is both creative and technically accurate:

* **The Orchestrator:** Acts as the Chief of Staff. It performs P1–P3 triage on incoming signals and routes tasks to the appropriate sub-agents.
* **The Strategist:** The narrative engine. It translates raw technical facts into compelling stories tailored for specific audience personas (e.g., C-Suite, Developers, Recruiters).
* **The Librarian:** The safety valve. It audits every generated claim against a local knowledge base (`heron_specs.txt`) to prevent hallucinations and ensure technical integrity.

---

## 🛠️ Tech Stack
* **Framework:** [Streamlit](https://streamlit.io/) (Frontend UI)
* **Orchestration:** [LangChain](https://www.langchain.com/) (Multi-agent workflows)
* **Models:** OpenAI GPT-4o & Anthropic Claude 3.5 Sonnet
* **Verification:** RAG-inspired grounding against local technical documentation.

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone [https://github.com/git-young-x/heron-velocity-engine.git](https://github.com/git-young-x/heron-velocity-engine.git)
cd heron-velocity-engine
