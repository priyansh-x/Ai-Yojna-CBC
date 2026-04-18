"""
Run this once to see which Gemini models your API key can access:
    GEMINI_API_KEY=your-key /Library/Frameworks/Python.framework/Versions/3.10/bin/python3 interface/check_models.py
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    print("Set GEMINI_API_KEY first.")
    sys.exit(1)

from google import genai
from google.genai import types

client = genai.Client(api_key=key)

# First: list ALL models the API reports for this key
print("\nAll models reported by ListModels:\n")
try:
    all_models = list(client.models.list())
    generate_capable = []
    for m in all_models:
        supported = getattr(m, 'supported_actions', []) or []
        if 'generateContent' in str(supported) or not supported:
            generate_capable.append(m.name)
            print(f"  {m.name}")
    print(f"\nTotal: {len(all_models)} models listed")
except Exception as e:
    print(f"  ListModels failed: {e}")
    generate_capable = []

# Second: test each one we guessed + any from ListModels
import time

candidates = list(dict.fromkeys(
    generate_capable +   # whatever ListModels said
    [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-8b",
        "gemini-1.0-pro",
    ]
))

print("\nTesting generateContent on each model:\n")
working = []
for i, name in enumerate(candidates[:8]):   # cap at 8 to avoid rate limits
    if i > 0:
        time.sleep(4)
    try:
        r = client.models.generate_content(
            model=name,
            contents="Reply with the single word: OK",
            config=types.GenerateContentConfig(max_output_tokens=5, temperature=0.0),
        )
        print(f"  ✓ {name}  →  {r.text.strip()}")
        working.append(name)
    except Exception as e:
        err = str(e)
        code = "404" if "404" in err else ("429" if "429" in err else "ERR")
        short = err[:80].replace('\n', ' ')
        print(f"  ✗ {name}  →  [{code}] {short}")

print()
if working:
    print(f"✓ Best model to use: {working[0]}")
else:
    print("✗ No models responded. The key may need billing enabled at aistudio.google.com.")
