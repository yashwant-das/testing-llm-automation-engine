"""
CLI entrypoint for the healing pipeline.

Re-exports the full public API of src.healing so callers do not need to
know the internal module layout.  The ``__main__`` block enables:

    python -m src.agents.healer tests/generated/broken.spec.ts [--max-retries N]
"""

from src.healing import (
    analyze_and_plan,
    apply_fix,
    attempt_healing,
    classify_failure_heuristic,
    emit_artifacts,
    extract_url_from_code,
    gather_evidence,
    run_test,
    verify_repair,
)

__all__ = [
    "analyze_and_plan",
    "apply_fix",
    "attempt_healing",
    "classify_failure_heuristic",
    "emit_artifacts",
    "extract_url_from_code",
    "gather_evidence",
    "run_test",
    "verify_repair",
]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Self-healing agent for automatically repairing broken Playwright tests."
    )
    parser.add_argument(
        "test_file", type=str, help="Path to the broken Playwright test file."
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum healing attempts (default: 3).",
    )
    args = parser.parse_args()
    print(attempt_healing(args.test_file, max_retries=args.max_retries))
