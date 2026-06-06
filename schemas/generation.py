"""
Pydantic schemas for the test generation pipeline.

GenerationResult wraps the TypeScript code extracted from an LLM response,
adding validation that ensures the code is non-empty and structurally sane
before it is written to disk or executed.
"""

from pydantic import BaseModel, Field, field_validator


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
