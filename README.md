# Next Best Action Platform

An **agentic decision-intelligence platform for SaaS Customer Success**. A Planner
agent reads a customer interaction, dynamically orchestrates specialist agents to
pull in company knowledge and diagnose the situation, and recommends the next best
actions — each with supporting evidence, a confidence score, a human in the loop,
and a memory that learns from past decisions.

The platform is **domain-agnostic by design**: the business logic lives in
`config/domain.yaml`, so the same engine can be pointed at a different B2B domain
(sales, staffing, support…) by editing config rather than code.

---

## What it does (end to end)

1. **Ingest** a raw interaction (email, call transcript, CSM notes) + the customer
   record into a clean structured situation.
2. **Plan** dynamically — deterministic business rules first, then an LLM planner
   that decides which agents to run for *this* situation.
3. **Retrieve** relevant playbooks / best practices from the knowledge base (RAG).
4. **Analyze** the situation, grounding findings in evidence and flagging
   **missing information**.
5. **Recommend** next best actions from a fixed catalogue, with evidence + confidence.
6. **Human-in-the-loop**: a person accepts / edits / rejects each recommendation.
7. **Learn**: every decision is written to shared memory and recalled on future runs.
8. **Measure**: an evaluation view turns the decision log into acceptance rates and
   revenue-outcome proxies.

---

## Architecture

**Sense → Plan → Act.**

- **Sense** — `ingestion` always runs first; you can't plan a response to a
  customer you haven't read.
- **Plan** — two layers (`planner.py`):
  1. **Deterministic business rules** (`config/domain.yaml`) fire on clear-cut
     cases (e.g. a healthy, quiet account short-circuits to "keep monitoring"
     with zero LLM calls) and act as a safety backstop.
  2. If no rule fires, an **LLM planning step** chooses which agents to run, in
     what order, and how deep to retrieve. Different customers take genuinely
     different routes, each with a stated reason.
- **Act** — the Planner executes the chosen steps through a **dispatch table**
  (agent name → handler), records an explainable **trace**, and returns one
  decision packet.

**Specialist agents** (`src/agents/`) share a small `Agent` contract:

| Agent | Role |
|-------|------|
| `ingestion` | Raw interaction + record → structured situation (signals, asks, sentiment). |
| `retrieval` | Embeds and searches the markdown knowledge base (in-memory cosine RAG). |
| `analysis` | Diagnoses situation type, risks, opportunities, and missing information. |
| `recommendation` | Picks catalogue actions with evidence + confidence; drops anything off-catalogue. |

**Shared memory** (`memory.py`) is a plain JSON store of human decisions. Before
recommending, the planner recalls similar past decisions (match on situation type
+ shared signals) and feeds them to the recommendation agent — so the system
learns from real choices instead of starting cold each time.

**Evaluation** (`metrics.py`, `pages/2_Evaluation.py`) treats every accept / edit /
reject as a labeled signal: acceptance rate per situation type and per action, plus
retention/expansion MRR proxies (decisions joined to customer MRR).

---

## Reusability: the `domain.yaml` story

Change the domain by editing one file, not the code:

- `next_best_actions` — the catalogue the platform may recommend.
- `agents` — which specialist agents the planner may schedule.
- `business_rules` — deterministic routing (e.g. `healthy_account.min_health_score`).
- `success_metrics` — what the domain tracks.

Adding a **new agent** is additive: list it in `agents:`, give it a dependency /
canonical position / description in `planner.py`'s constants, write the agent class,
and register one handler in the dispatch table. The execution loop never changes.

---

## Setup (about 10 minutes)

1. **Install Python 3.10+** — check with `python --version`.
2. **Get a free Gemini API key** (no credit card) at
   https://aistudio.google.com/apikey.
3. **Add your key:** copy `.env.example` to `.env`, paste your key after
   `GEMINI_API_KEY=`. (`.env` is gitignored — never commit it.)
4. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
5. **Test it:**
   ```
   python src/test_setup.py
   ```

---

## Running it

**Web UI (recommended)** — analyze customers, review the plan/evidence, and
accept/edit/reject (this is where the learning loop closes):
```
streamlit run src/app.py
```
The sidebar has an **Evaluation** page for measurable outcomes.

**CLI** — print decision packets:
```
python src/run.py                 # all customers
python src/run.py acme            # one customer
python src/run.py acme globex     # several
```

**Record a decision from the CLI** (closes the loop headless):
```
python src/run.py acme --accept escalate --note "Exec call booked"
python src/run.py initech --reject propose_upsell
```

**Seed memory** so the learning + evaluation views are populated for a demo
(no LLM calls):
```
python src/seed_memory.py          # seed
python src/seed_memory.py --show   # inspect
python src/seed_memory.py --clear  # wipe
```

**Evaluation report (CLI):**
```
python src/metrics.py
```

---

## Project layout

```
config/domain.yaml          # the domain config (swap this to change domains)
data/
  customers.json            # synthetic customer records
  knowledge/*.md            # playbooks / best practices (the RAG corpus)
  interactions/*.txt        # synthetic emails, transcripts, notes
  memory.json               # decision log (generated; gitignored)
  cache/                    # cached packets (generated; gitignored)
src/
  llm.py                    # thin Gemini wrapper (chat / chat_json)
  config.py                 # shared paths + domain config loader
  planner.py                # orchestrator: rules + dynamic plan + dispatch table
  run_pipeline.py           # library entry point (+ optional caching)
  run.py                    # CLI
  app.py                    # Streamlit UI (human-in-the-loop)
  pages/2_Evaluation.py     # measurable-outcomes dashboard
  memory.py                 # shared memory / learning loop
  metrics.py                # evaluation engine
  seed_memory.py            # demo seeder
  cache.py                  # disk cache for packets
  agents/                   # ingestion, retrieval, analysis, recommendation
```

---

## Notes on the free Gemini tier

Each analysis makes several LLM calls, and the free tier has a small **per-day**
request cap that resets at midnight Pacific Time (limits are per Google Cloud
project, not per key). If you hit a `429 RESOURCE_EXHAUSTED`: keep "Use cached
result" on in the UI (analyze each customer once, then replay for free), run fewer
customers, wait for the reset, or enable billing for higher limits.

The free tier may use prompts to improve Google's models, so **don't send real or
confidential data** — everything in `data/` is synthetic, which is exactly the point.
