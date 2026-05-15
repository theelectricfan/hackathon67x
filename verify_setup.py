"""
Run this before starting the agent to verify all credentials are set.

Usage: python verify_setup.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS = [
    # (env_var_name, label, required_for, is_optional)
    ("LLM_GATEWAY_URL",      "LLM_GATEWAY_URL      ", "Core LLM",       False),
    ("LLM_GATEWAY_KEY",      "LLM_GATEWAY_KEY      ", "Core LLM",       False),
    ("ANTHROPIC_API_KEY",    "ANTHROPIC_API_KEY    ", "Core LLM",       False),
    ("PARALLEL_API_KEY",     "PARALLEL_API_KEY     ", "Parallel AI",    False),
    ("LANGFUSE_PUBLIC_KEY",  "LANGFUSE_PUBLIC_KEY  ", "Observability",  True),
    ("LANGFUSE_SECRET_KEY",  "LANGFUSE_SECRET_KEY  ", "Observability",  True),
    ("LANGFUSE_HOST",        "LANGFUSE_HOST        ", "Observability",  True),
]

print()
print("  BL RCA Agent — Setup Verification")
print("  " + "─" * 42)

status = {}

for key, label, group, optional in CREDENTIALS:
    val = os.getenv(key)
    is_set = bool(val and val.strip())

    if is_set:
        icon = "✅"
        note = "set"
    elif optional:
        icon = "⚠️ "
        note = "missing (optional)"
    else:
        icon = "❌"
        note = "missing"

    print(f"  {icon}  {label}  {note}")

    if group not in status:
        status[group] = True
    if not is_set and not optional:
        status[group] = False

print()
print("  " + "─" * 42)
print("  Summary")
print("  " + "─" * 42)

labels = {
    "Core LLM":      "Core LLM (Gateway + Anthropic)",
    "Parallel AI":   "Parallel AI",
    "Observability": "Observability (Langfuse)",
}

all_core_ready = True
for group, ready in status.items():
    icon = "✅" if ready else "❌"
    state = "Ready" if ready else "Not Ready"
    print(f"  {icon}  {labels.get(group, group):<35} {state}")
    if group == "Core LLM" and not ready:
        all_core_ready = False

print()
if all_core_ready:
    print("  ✅  Agent can start. Run: python main.py data/sample_unsold_bls.csv")
else:
    print("  ❌  Fill in missing credentials in .env before running the agent.")
print()
