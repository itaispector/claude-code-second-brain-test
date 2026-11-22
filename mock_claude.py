#!/usr/bin/env python3
"""Fake `claude -p` for testing the harness. Answers are canned, NOT real results."""
import json, os, random, sys
from pathlib import Path

args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
arm = os.environ.get("MOCK_ARM", "none")
probe = "--allowedTools" in args

if not probe:
    if arm.startswith("native"):
        d = Path(os.environ["MOCK_MEMDIR"]); d.mkdir(parents=True, exist_ok=True)
        (d / f"note_{random.randint(0, 9999)}.md").write_text(prompt[:200])
    if arm == "vault":
        n = Path(os.environ["MOCK_VAULT"]) / "notes"
        (n / f"note_{random.randint(0, 9999)}.md").write_text(prompt[:200])
    answer = "Done."
else:
    canned = {
        "package manager": "bun", "legacy": "No, the distributor runs it nightly.", "main contact": "Dana",
        "Redis": "It runs on a $5 VPS.", "release window": "February 2027", "logging": "Use src/log.js",
        "backup contact": "Yossi", "other project": "bun",
    }
    key = next((k for k in canned if k.lower() in prompt.lower()), None)
    answer = canned.get(key, "UNKNOWN") if random.random() < {"none": 0.3, "native": 0.75, "vault": 0.8, "native_rules": 0.8}[arm] else "UNKNOWN"

print(json.dumps({
    "result": "MOCK: " + answer, "is_error": False, "num_turns": 1, "total_cost_usd": 0.0,
    "usage": {"input_tokens": random.randint(8000, 20000), "output_tokens": 50,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
    "permission_denials": [],
}))
