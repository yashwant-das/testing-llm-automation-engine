"""
Pydantic schemas for the test generation and vision pipelines.

GenerationResult   — validates raw LLM code output before writing to disk.
GenerationDecision — full provenance artifact for a generation run (to tests/artifacts/).
VisionDecision     — full provenance artifact for a vision run (to tests/artifacts/).
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .artifacts import ContextSnapshot
from .shared import ProvenanceRecord


class GenerationResult(BaseModel):
    """
    Validated result of a Playwright test generation call.

    The LLM may return the code in a markdown block, as raw text, or prefixed
    with explanatory prose. This model normalises the extracted code and
    validates it is non-empty before returning it to the caller.
    """

    code: str = Field(description="Generated TypeScript Playwright test code.")

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Generated code is empty.")
        return stripped

    @property
    def has_playwright_import(self) -> bool:
        """True if the code imports from @playwright/test."""
        return "@playwright/test" in self.code

    @property
    def has_test_block(self) -> bool:
        """True if the code contains at least one test() or it() block."""
        return "test(" in self.code or "it(" in self.code

    @property
    def line_count(self) -> int:
        """Number of lines in the generated code."""
        return len(self.code.splitlines())


class GenerationDecision(ProvenanceRecord):
    """Full provenance artifact for a test generation run.

    Written to tests/artifacts/ as generation_decision_*.json after each run.
    Mirrors HealingDecision's provenance contract so both appear uniformly in
    the Artifact Inspector.
    """

    pipeline: str = "generation"
    url: str
    story: str
    code: str
    line_count: int = Field(default=0, ge=0)
    context_snapshot: Optional[ContextSnapshot] = None

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown report for the Artifact Inspector."""
        model_str = (
            f"{self.model_used} ({self.provider})"
            if self.model_used and self.provider
            else self.model_used or "*(unknown)*"
        )
        prompt_str = (
            f"`{self.prompt_version}` (hash: `{self.prompt_hash}`)"
            if self.prompt_version or self.prompt_hash
            else "*(unknown)*"
        )
        duration_str = (
            f"{self.latency_ms} ms" if self.latency_ms else "*(not recorded)*"
        )
        tokens_str = (
            f"{self.input_tokens:,} in / {self.output_tokens:,} out"
            if self.input_tokens or self.output_tokens
            else "*(not recorded)*"
        )
        trace_str = f"`{self.trace_id}`" if self.trace_id else "*(n/a)*"
        snapshot_str = (
            f"`{self.context_snapshot_id}`" if self.context_snapshot_id else "*(n/a)*"
        )
        ctx_parts: list[str] = []
        if self.context_snapshot:
            snap = self.context_snapshot
            if snap.html:
                excerpt = snap.html[:500].replace("```", "` ` `")
                ctx_parts.append(f"**DOM (first 500 chars):**\n```html\n{excerpt}\n```")
            if snap.accessibility_tree:
                excerpt = snap.accessibility_tree[:500]
                ctx_parts.append(
                    f"**Accessibility Tree (first 500 chars):**\n```\n{excerpt}\n```"
                )
            if snap.locator_candidates:
                cands = "\n".join(f"- `{c}`" for c in snap.locator_candidates[:10])
                ctx_parts.append(f"**Locator Candidates:**\n{cands}")
            if snap.console_errors:
                errs = "\n".join(f"- {e}" for e in snap.console_errors[:5])
                ctx_parts.append(f"**Console Errors:**\n{errs}")
        ctx_md = "\n\n".join(ctx_parts) if ctx_parts else "*(no page context captured)*"

        return f"""# Generation Report: {self.timestamp}

**URL:** `{self.url}`
**Scenario:** {self.story}

## Generated Test

```typescript
{self.code}
```

*{self.line_count} lines*

## Context Snapshot

*Snapshot ID: {snapshot_str}*

{ctx_md}

## Provenance

- **Model:** {model_str}
- **Prompt Version:** {prompt_str}
- **Latency:** {duration_str}
- **Tokens:** {tokens_str}
- **Trace:** {trace_str}
"""


class VisionDecision(ProvenanceRecord):
    """Full provenance artifact for a vision generation run.

    Written to tests/artifacts/ as vision_decision_*.json after each run.
    Includes the screenshot path so the artifact links to the visual input.
    """

    pipeline: str = "vision"
    url: str
    instruction: str
    code: str
    line_count: int = Field(default=0, ge=0)
    screenshot_path: Optional[str] = None

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown report for the Artifact Inspector."""
        model_str = (
            f"{self.model_used} ({self.provider})"
            if self.model_used and self.provider
            else self.model_used or "*(unknown)*"
        )
        prompt_str = (
            f"`{self.prompt_version}` (hash: `{self.prompt_hash}`)"
            if self.prompt_version or self.prompt_hash
            else "*(unknown)*"
        )
        duration_str = (
            f"{self.latency_ms} ms" if self.latency_ms else "*(not recorded)*"
        )
        tokens_str = (
            f"{self.input_tokens:,} in / {self.output_tokens:,} out"
            if self.input_tokens or self.output_tokens
            else "*(not recorded)*"
        )
        trace_str = f"`{self.trace_id}`" if self.trace_id else "*(n/a)*"
        screenshot_md = (
            f"![Screenshot](/gradio_api/file={self.screenshot_path})"
            if self.screenshot_path
            else "*(not captured)*"
        )

        return f"""# Vision Report: {self.timestamp}

**URL:** `{self.url}`
**Instruction:** {self.instruction}

## Screenshot

{screenshot_md}

## Generated Test

```typescript
{self.code}
```

*{self.line_count} lines*

## Provenance

- **Model:** {model_str}
- **Prompt Version:** {prompt_str}
- **Latency:** {duration_str}
- **Tokens:** {tokens_str}
- **Trace:** {trace_str}
"""
