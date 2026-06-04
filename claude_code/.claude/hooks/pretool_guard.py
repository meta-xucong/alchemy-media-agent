#!/usr/bin/env python3
"""Example Claude Code hook: block obvious secret leakage and destructive commands.
This is a skeleton. Wire it into Claude Code hooks config according to your environment.
"""
import json
import re
import sys

payload = json.load(sys.stdin)
text = json.dumps(payload, ensure_ascii=False)

secret_patterns = [r"sk-[A-Za-z0-9_-]{20,}", r"OPENAI_API_KEY\s*=\s*\S+", r"ANTHROPIC_API_KEY\s*=\s*\S+"]
if any(re.search(p, text) for p in secret_patterns):
    print(json.dumps({"decision": "block", "reason": "Possible API key exposure detected."}))
    sys.exit(0)

if "rm -rf /" in text or "chmod -R 777 /" in text:
    print(json.dumps({"decision": "block", "reason": "Dangerous shell command blocked."}))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
