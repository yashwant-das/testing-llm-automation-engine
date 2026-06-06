# Prompt Management Overview

> How prompts are stored, versioned, and loaded.

---

## Storage

All LLM system prompts are external markdown files in `prompts/`:

```text
prompts/
├── generator.md      # DOM-based test generation
├── healer.md         # Failure diagnosis and code repair
├── vision.md         # Visual test generation from screenshots
└── manifest.json     # Version registry
```

Prompts are loaded at runtime by `src/utils/prompt_loader.py`. They are not embedded in Python source code.

**Why external files?**

- Diffable in git — prompt changes show as clear text diffs
- Human-editable without Python syntax awareness
- Independently versioned (changing a prompt does not require a code release)
- Searchable with standard text tools

---

## Version Registry (`manifest.json`)

```json
{
  "version": "1.0.0",
  "description": "...",
  "prompts": {
    "healer": {
      "version": "2",
      "description": "Test failure healer and analyzer"
    },
    "generator": {
      "version": "1",
      "description": "Playwright test generator"
    },
    "vision": {
      "version": "1",
      "description": "Visual Playwright test generator"
    }
  }
}
```

The `version` field is a human-set label. It is incremented manually when the prompt content is intentionally changed. The content hash is always computed dynamically from the file.

**Rule:** The `version` label signals intent ("this is a different version"). The `prompt_hash` signals reality ("this is the exact content that was used"). Both are recorded in every benchmark run and healing artifact.

---

## Loading a Prompt

```python
from src.utils.prompt_loader import load_prompt, get_prompt_version, get_prompt_hash

# Load raw content (with Python format placeholders intact)
content = load_prompt("healer")
# → "You are an Expert QA Automation Engineer...\n{{failure_type}}..."

# Fill placeholders
system_prompt = content.format(failure_type=h_type.value, confidence=h_conf, reason=h_reason)

# Get version and hash for provenance recording
version = get_prompt_version("healer")   # "2"
hash_ = get_prompt_hash("healer")        # "abc123def456abcd" (first 16 hex of SHA-256)
```

`_load_manifest()` caches the manifest after the first read. `load_prompt()` reads the file on every call (no caching — the file may change between calls in development).

---

## Prompt Format Conventions

All prompts use Python-style `{placeholder}` format strings where the calling code injects runtime values. Use `{{` and `}}` for literal braces in the prompt (e.g., JSON schema examples in the output format section).

The healer prompt injects:

- `{failure_type}` — the heuristic pre-diagnosis (e.g., "TIMEOUT")
- `{confidence}` — the heuristic confidence (e.g., "1.00")
- `{reason}` — the heuristic reason string

The generator and vision prompts do not inject format values — they are fixed system prompts.

---

## See Also

- [`healing.md`](healing.md) — healer prompt design
- [`generation.md`](generation.md) — generator prompt design
- [`versioning.md`](versioning.md) — when and how to increment versions
