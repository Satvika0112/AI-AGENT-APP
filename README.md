# Next Best Action Platform

An agentic decision-intelligence platform for **SaaS Customer Success**.
A Planner agent orchestrates specialist agents to read a customer interaction,
pull in company knowledge, analyse the situation, and recommend the next best
actions — each with supporting evidence, a confidence score, and a human in the loop.

> This is the Day 1 starter. The agents, planner, memory, and UI get added next.

## What's here so far
- `src/llm.py` — one small wrapper around the free Google Gemini API
- `src/test_setup.py` — a quick check that your setup works
- `config/domain.yaml` — the business config (swap THIS to change domains = reusability)
- `data/` — synthetic customers, interactions, and a small knowledge base

## Setup (about 10 minutes)

1. **Install Python 3.10+** if you don't have it. Check with `python --version`.

2. **Get a free Gemini API key** (no credit card):
   - Go to https://aistudio.google.com/apikey
   - Sign in with a Google account, click "Create API key", copy it.

3. **Add your key:**
   - Copy `.env.example` to a new file called `.env`
   - Paste your key after `GEMINI_API_KEY=`

4. **Install the dependencies:**
   ```
   pip install -r requirements.txt
   ```

5. **Test it:**
   ```
   python src/test_setup.py
   ```
   If you see a sentence from the model and "Setup works!", you're ready.

## Note on the free tier
The free Gemini tier may use your prompts to improve Google's models, so don't send
real or confidential data. Everything in `data/` is made up — exactly what we want.
