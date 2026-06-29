# Next Best Action

A decision-support tool for SaaS Customer Success teams. It reads a real customer interaction (an email, a call transcript, a CSM's notes), works out what's actually going on with that account, and suggests the one or two things worth doing next. A human signs off on every suggestion, and the system remembers those decisions so its next suggestion is a little better.

We built it around a simple frustration: a CSM managing 40 accounts can't read every signal in time. Usage dips, a champion quietly leaves, someone fires off an email asking about pricing. The information is all there, but it's scattered and nobody has the hours to triage it. This is a small engine that does the triage and hands back a recommendation you can accept, edit, or throw out.

The whole thing is also domain-agnostic on purpose. The business logic lives in one config file, so the same engine could be pointed at sales, support, or staffing by editing config instead of rewriting code. More on that below.

---

## The problem it solves

Customer Success is reactive by default. You usually find out an account is unhappy when they tell you they're leaving, which is the worst possible time to find out. The accounts that need attention and the accounts that are fine look similar from a dashboard. What you actually want is a short, ranked list every morning: *these three accounts need you today, and here's why.*

That's the job here. Given what we know about a customer plus their latest interaction, decide whether this is a churn risk, an upsell opening, an onboarding gap, or nothing that needs action yet, and recommend a next step grounded in evidence rather than a gut feeling.

---

## How it works, end to end

A customer interaction comes in and moves through a short pipeline:

1. **Ingest.** Read the raw interaction and the customer record, and turn the mess into a clean structured summary: what they asked for, what the warning signs are, the overall sentiment. This step only reports what it sees. It doesn't diagnose.
2. **Plan.** Decide what to do with this specific customer. Deterministic business rules run first (a healthy, quiet account skips straight to "keep monitoring" with no AI calls at all). If no rule applies, an LLM planning step picks which specialist agents to run and in what order. Different accounts genuinely take different routes.
3. **Retrieve.** Pull the relevant playbooks from the knowledge base. If the account looks like churn, it fetches the churn playbook, not the upsell one.
4. **Analyze.** Diagnose the situation against the customer's facts and the retrieved playbooks, ground every finding in a piece of evidence, and flag anything important that's missing from the inputs.
5. **Recommend.** Choose the next best action from a fixed catalogue (no inventing actions), each with a rationale, supporting evidence, and a confidence score.
6. **Human in the loop.** A person accepts, edits, or rejects each recommendation. Nothing is sent automatically.
7. **Learn.** Every decision is written to shared memory. On the next run, the system recalls similar past decisions and feeds them into the recommendation step.
8. **Measure.** An evaluation view turns the decision log into acceptance rates, plus an offline accuracy check against a small set of known-answer cases.

---

## Architecture

The mental model is **sense, plan, act.**

**Sense** is ingestion. It always runs first, because you can't plan a response to a customer you haven't read yet. It's perception, not a decision.

**Plan** has two layers, both in `planner.py`:

- *Deterministic business rules* run first. They live in `config/domain.yaml` and handle clear-cut cases. A healthy account with a high health score, no warning signals, and no open questions short-circuits to "keep monitoring" and spends zero on AI calls. These rules are also a safety backstop, so the obvious cases stay predictable.
- If no rule fires, an *LLM planning step* looks at the situation and chooses which agents to schedule. It's told what each agent does and what depends on what, so its plan is informed and, just as importantly, explainable.

**Act** runs the chosen plan through a dispatch table that maps an agent's name to its handler. It records a trace of what ran and why, so you can always see the reasoning afterward. If planning ever fails or returns nothing usable, it falls back to running the full pipeline, so a bad plan is never worse than the old static behaviour.

### The agents

All four follow the same tiny contract (a `name` and a `run()` method) defined in `agents/base.py`.

| Agent | What it does |
|-------|--------------|
| `ingestion` | Raw interaction plus customer record, turned into a structured situation: signals, customer asks, sentiment. |
| `retrieval` | Embeds the markdown knowledge base and finds the most relevant sections for the situation. Uses an in-memory cosine search rather than a vector DB. |
| `analysis` | Diagnoses the situation type, the risks, the opportunities, and the missing information. Does not pick the action. |
| `recommendation` | Picks actions from the catalogue with evidence and confidence, and drops anything that isn't on the approved list. |

### Shared memory (the learning loop)

`memory.py` is a plain JSON store of human decisions. Before recommending, the planner asks it for similar past cases. The similarity score is deliberately boring and easy to explain: three points if the situation type matches, one point for each shared signal keyword. We kept it simple on purpose so you can read a recall and understand exactly why it surfaced. You could swap it for a vector store later without touching the planner.

### Why these choices

A few decisions we'd defend in the walkthrough:

- **Rules before the model.** The clear cases shouldn't cost an API call or risk a hallucination. Rules are cheaper, faster, and predictable, and they double as guardrails.
- **A dispatch table, not an if/else chain.** Adding a new agent is additive: list it in `domain.yaml`, give it a dependency and a one-line description in the planner, write the class, register one handler. The execution loop never changes.
- **A fixed action catalogue.** The recommendation agent can only choose from actions in `domain.yaml`. Anything it invents gets filtered out before a human sees it. This keeps the tool honest in a domain where a wrong "send renewal" email has real consequences.
- **Human in the loop, always.** `requires_human_review` is forced to true in code, not left to the model's discretion.
- **Synthetic data only.** Everything in `data/` is made up. The free Gemini tier may use prompts to improve Google's models, so real customer data has no business here, and for a demo it doesn't need to.

---

## Reusability: the `domain.yaml` story

This is the part we're proudest of. The business knowledge is config, not code. To change what the platform does, you edit one file:

- `next_best_actions` — the catalogue of actions it's allowed to recommend.
- `agents` — which specialist agents the planner may schedule.
- `business_rules` — deterministic routing, like the healthy-account health-score threshold.
- `success_metrics` — what the domain cares about measuring.

Point it at a different B2B domain by rewriting those lists. The pipeline, the planner, and the agents don't change.

---

## Setup

You'll need about ten minutes and a free API key.

1. **Python 3.10 or newer.** Check with `python --version`.
2. **A free Gemini API key**, no credit card, from https://aistudio.google.com/apikey.
3. **Add your key.** Copy `.env.example` to `.env` and paste your key after `GEMINI_API_KEY=`. The `.env` file is gitignored, so don't commit it.
4. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
5. **Confirm it works:**
   ```
   python src/test_setup.py
   ```
   If you get a friendly one-sentence reply from the model, you're set.

---

## Running it

### Web UI (recommended)

This is where the human-in-the-loop part lives. Pick a customer, review the plan and the evidence, and accept, edit, or reject the recommendations.

```
streamlit run src/app.py
```

The sidebar has an Evaluation page for the measurable side of things.

### Command line

Print decision packets without the UI:

```
python src/run.py                 # every customer
python src/run.py acme            # one customer
python src/run.py acme globex     # a few
```

Record a decision headless (this closes the learning loop the same way the UI does):

```
python src/run.py acme --accept escalate --note "Exec call booked"
python src/run.py initech --reject propose_upsell
```

### Seed the memory for a demo

So the learning and evaluation views aren't empty when you present. No AI calls involved.

```
python src/seed_memory.py          # seed
python src/seed_memory.py --show   # inspect
python src/seed_memory.py --clear  # wipe
```

### Evaluation report from the CLI

```
python src/metrics.py
```

---

## A note on the free Gemini tier

Each analysis makes a handful of LLM calls, and the free tier has a small per-day cap that resets at midnight Pacific. The limit is per Google Cloud project, not per key. If you hit a `429 RESOURCE_EXHAUSTED`, you have options: keep "Use cached result" on in the UI so you analyze each customer once and replay for free afterward, run fewer customers at a time, wait for the reset, or enable billing for higher limits.

The caching matters for demos. Analyze each account once, and every replay after that is free and instant, which keeps a live demo from dying on a quota error in front of an audience.

---

## Project layout

```
config/domain.yaml          # the domain config (swap this to change domains)
data/
  customers.json            # synthetic customer records
  knowledge/*.md            # playbooks and best practices (the RAG corpus)
  interactions/*.txt        # synthetic emails, transcripts, notes
  memory.json               # decision log (generated, gitignored)
  cache/                    # cached packets (generated, gitignored)
src/
  llm.py                    # thin Gemini wrapper (chat / chat_json)
  config.py                 # shared paths and domain config loader
  planner.py                # the orchestrator: rules, dynamic plan, dispatch table
  run_pipeline.py           # library entry point
  run.py                    # CLI
  app.py                    # Streamlit UI (human-in-the-loop)
  pages/2_evaluation.py     # measurable-outcomes dashboard
  memory.py                 # shared memory and learning loop
  metrics.py                # evaluation engine
  seed_memory.py            # demo seeder
  cache.py                  # disk cache for packets
  agents/                   # ingestion, retrieval, analysis, recommendation
```
