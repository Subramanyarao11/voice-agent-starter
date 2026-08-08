"""Evaluation dashboard rollup contracts."""

import importlib

_evaluation_metrics = importlib.import_module(
    "scripts.12_run_evaluations"
)._evaluation_metrics


def test_evaluation_metrics_roll_up_latency_and_language_quality() -> None:
    metrics = _evaluation_metrics(
        [
            {"language": "kn", "passed": True, "duration_ms": 100.0},
            {"language": "kn", "passed": False, "duration_ms": 200.0},
            {"language": "hi", "passed": True, "duration_ms": 50.0},
        ]
    )

    assert metrics["case_count"] == 3
    assert metrics["passed_count"] == 2
    assert metrics["average_duration_ms"] == 116.67
    assert metrics["p95_duration_ms"] == 200.0
    assert metrics["by_language"]["kn"]["pass_rate"] == 0.5
    assert metrics["by_language"]["hi"]["average_duration_ms"] == 50.0
