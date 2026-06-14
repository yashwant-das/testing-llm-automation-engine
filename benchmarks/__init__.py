"""
Evaluation and benchmarking framework — Phase 7.

Provides reproducible benchmarks for the generation and healing pipelines.
Every run records the model, prompt hash, dataset version, and per-example
scores so results can be compared across model or prompt changes.

Sub-packages:
    generation/         Evaluate generated Playwright test code quality.
    healing/            Evaluate failure classification and repair accuracy.
    intent_validation/  Validate that generated tests cover the stated intent.
    mutations/          Programmatically introduce known failures for fixtures.
    datasets/           Dataset format documentation.
    reports/            Output directory for saved BenchmarkRun JSON files.

Usage:
    from benchmarks.generation.runner import run_generation_benchmark
    from benchmarks.healing.runner import run_healing_benchmark
"""
