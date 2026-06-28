"""
llm.py - a tiny wrapper around the (free) Google Gemini API.

Why this file exists:
  Every agent in the platform needs to "ask the LLM something".
  Instead of repeating the API setup everywhere, we centralise it here.
  If you ever switch providers (OpenAI, Claude, Groq...), you only change THIS file.
"""

import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY from your .env file

_API_KEY = os.getenv("GEMINI_API_KEY")
if not _API_KEY:
    raise RuntimeError(
        "No GEMINI_API_KEY found. Copy .env.example to .env and paste your free key "
        "from https://aistudio.google.com/apikey"
    )

# Gemini 2.5 Flash is free, fast, and smart enough for this project.
MODEL = "gemini-2.5-flash"

_client = genai.Client(api_key=_API_KEY)


def chat(prompt: str, system: str = "") -> str:
    """Send a prompt to the LLM and get back plain text."""
    contents = prompt if not system else f"{system}\n\n{prompt}"
    for attempt in range(4):  # simple retry for free-tier rate limits (429s)
        try:
            resp = _client.models.generate_content(model=MODEL, contents=contents)
            return (resp.text or "").strip()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)  # wait 1s, 2s, 4s, then retry


def chat_json(prompt: str, system: str = "") -> dict:
    """Like chat(), but forces the model to return JSON and parses it.
    We'll use this for the Planner so it can return structured decisions."""
    guard = "Respond with ONLY valid JSON. No markdown, no backticks, no explanation."
    raw = chat(prompt, system=(system + "\n" + guard).strip())
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")  # last resort: grab the {...}
        return json.loads(raw[start:end + 1])
