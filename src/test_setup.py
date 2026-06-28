"""
test_setup.py - run this FIRST to confirm your setup works.

    python src/test_setup.py

If you see a friendly reply from the model, you're ready to build.
"""
from llm import chat

print("Asking the model a test question...\n")
reply = chat("In one sentence, what is a 'next best action' in customer success?")
print("Model replied:\n")
print(reply)
print("\n[OK] Setup works! You're ready for the next step.")
