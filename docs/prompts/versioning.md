# Prompt Versioning

> When and how to increment prompt versions.

---

## Two-Signal Versioning

Every prompt has two identifiers:

| Identifier | Source | Meaning |
| --- | --- | --- |
| `version` | `prompts/manifest.json` | Human-set intent label — "this is a different version" |
| `prompt_hash` | SHA-256 of file content | Reality — "this is the exact bytes that ran" |

The version label is for humans. The hash is for machines. Both are recorded in every `HealingDecision` artifact and every `BenchmarkRunConfig`.

---

## When to Increment the Version

Increment `version` in `manifest.json` when you make an intentional change to a prompt that you expect will affect outputs. This signals to the team that the prompt changed deliberately.

**Do increment when:**

- Adding or removing a required output field (e.g., adding `confidence_rationale`)
- Changing the repair strategy selection guide
- Revising the persona or framing
- Fixing a factual error in the instructions
- Changing truncation limits in the user message

**Do not increment when:**

- Fixing a typo that does not affect meaning
- Adding whitespace or formatting
- Adding a comment that the LLM never sees

---

## How to Increment

1. Edit the prompt file (`prompts/healer.md`, etc.)
2. Open `prompts/manifest.json` and increment the `version` string
3. Commit both files together

```json
{
  "prompts": {
    "healer": {
      "version": "3",
      "description": "Added JSON schema validation hints"
    }
  }
}
```

The `prompt_hash` updates automatically — it is always computed fresh from the file content. Do not hard-code the hash in `manifest.json`.

---

## Verifying a Change

After editing a prompt, verify the hash changed:

```python
from src.utils.prompt_loader import get_prompt_hash, get_prompt_version
print(get_prompt_version("healer"))   # should show new version
print(get_prompt_hash("healer"))      # should be different from the previous hash
```

---

## Finding What Prompt Was Used for a Decision

Every `HealingDecision` artifact records:

```json
{
  "prompt_version": "2",
  "prompt_hash": "abc123def456abcd"
}
```

To find the prompt content for that hash:

```bash
# Compute the hash of the current prompt
python3 -c "
import hashlib
from pathlib import Path
content = Path('prompts/healer.md').read_text()
print(hashlib.sha256(content.encode()).hexdigest()[:16])
"
# If it matches abc123def456abcd, the prompt is unchanged since that decision.
# If it differs, check git history for when healer.md last changed.

# Find the commit that changed the prompt
git log --oneline prompts/healer.md
```

---

## Prompt Hash in Benchmark Runs

`BenchmarkRunConfig.prompt_hash` records the prompt hash at run time. When comparing two runs:

- Same `prompt_hash` → same prompt content → results are comparable
- Different `prompt_hash` → prompt changed between runs → comparison is confounded

Always compare runs with identical `prompt_hash` when the goal is to measure model or dataset changes.
