import unittest
from unittest.mock import patch

from prometheus_client import REGISTRY

from langfuse_client import extract_trace_metrics
from metrics import (
    clear_daily_gauges,
    clear_gauges,
    update_from_daily_rows,
    update_from_traces,
)


class UpdateFromDailyRowsTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_gauges()

    def test_empty_api_response_emits_zero_metrics_for_today(self) -> None:
        with patch("metrics._today_utc", return_value="2025-06-16"):
            update_from_daily_rows("demo", [])

        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_daily_traces",
                {"project": "demo", "date": "2025-06-16"},
            ),
            0.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_tokens_total",
                {"project": "demo", "date": "2025-06-16", "model": "none"},
            ),
            0.0,
        )

    def test_daily_row_without_usage_emits_zero_token_metrics(self) -> None:
        update_from_daily_rows(
            "demo",
            [
                {
                    "date": "2025-06-15",
                    "countTraces": 3,
                    "countObservations": 5,
                    "totalCost": 0,
                    "usage": [],
                }
            ],
        )

        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_daily_traces",
                {"project": "demo", "date": "2025-06-15"},
            ),
            3.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_tokens_total",
                {"project": "demo", "date": "2025-06-15", "model": "none"},
            ),
            0.0,
        )

    def test_usage_row_exports_token_metrics(self) -> None:
        update_from_daily_rows(
            "demo",
            [
                {
                    "date": "2025-06-15",
                    "countTraces": 1,
                    "countObservations": 1,
                    "totalCost": 0.01,
                    "usage": [
                        {
                            "model": "gpt-4",
                            "totalUsage": 100,
                            "inputUsage": 60,
                            "outputUsage": 40,
                            "totalCost": 0.01,
                            "countTraces": 1,
                            "countObservations": 1,
                        }
                    ],
                }
            ],
        )

        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_tokens_total",
                {"project": "demo", "date": "2025-06-15", "model": "gpt-4"},
            ),
            100.0,
        )
        self.assertIsNone(
            REGISTRY.get_sample_value(
                "langfuse_tokens_total",
                {"project": "demo", "date": "2025-06-15", "model": "none"},
            ),
        )


class ExtractTraceMetricsTest(unittest.TestCase):
    def test_extracts_ttft_tokens_and_underscore_labels(self) -> None:
        extracted = extract_trace_metrics(
            {
                "id": "66000000000000000000000000000000",
                "metadata": {
                    "AI_TTFT_Ms": 11026,
                    "inputTokens": 33,
                    "outputTokens": 156,
                    "totalTokens": 189,
                    "model": "qwen/qwen3.6-27b",
                    "n8n_node_name": "AI Agent",
                    "n8n_workflow_name": "Demo Agent TTFT Langfuse",
                    "n8n_workflow_id": "wf-123",
                    "executionId": 660,
                },
            }
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertEqual(extracted["ttft_ms"], 11026.0)
        self.assertEqual(extracted["input_tokens"], 33.0)
        self.assertEqual(extracted["node_name"], "AI Agent")
        self.assertEqual(extracted["execution_id"], "660")
        self.assertEqual(extracted["workflow_id"], "wf-123")
        self.assertEqual(extracted["workflow"], "Demo Agent TTFT Langfuse")

    def test_reads_ttft_from_output_and_string_metadata(self) -> None:
        extracted = extract_trace_metrics(
            {
                "id": "t2",
                "metadata": '{"executionId": 652, "model": "qwen/qwen3.6-27b"}',
                "output": {
                    "AI_TTFT_Ms": 10852,
                    "inputTokens": 10,
                    "outputTokens": 20,
                    "totalTokens": 30,
                },
            }
        )
        self.assertEqual(extracted["ttft_ms"], 10852.0)
        self.assertEqual(extracted["execution_id"], "652")
        self.assertEqual(extracted["total_tokens"], 30.0)

    def test_falls_back_to_dotted_metadata_keys(self) -> None:
        extracted = extract_trace_metrics(
            {
                "id": "abc",
                "metadata": {
                    "AI_TTFT_Ms": 500,
                    "n8n.node.name": "AI Agent",
                    "n8n.workflow.name": "Demo",
                    "n8n.workflow.id": "wf-dotted",
                },
            }
        )
        self.assertEqual(extracted["node_name"], "AI Agent")
        self.assertEqual(extracted["workflow"], "Demo")
        self.assertEqual(extracted["workflow_id"], "wf-dotted")

    def test_skips_traces_without_ai_metrics(self) -> None:
        self.assertIsNone(
            extract_trace_metrics({"id": "x", "metadata": {"foo": "bar"}})
        )


class UpdateFromTracesTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_daily_gauges()
        # Isolate seen-trace state per test project name
        from metrics import _SEEN, _SEEN_SET

        _SEEN.clear()
        _SEEN_SET.clear()

    def test_increments_counters_and_ttft_once_per_trace(self) -> None:
        rows = [
            {
                "trace_id": "t1",
                "ttft_ms": 1000.0,
                "input_tokens": 10.0,
                "output_tokens": 20.0,
                "total_tokens": 30.0,
                "model": "m1",
                "node_name": "AI Agent",
                "workflow": "Demo",
                "workflow_id": "wf-1",
                "execution_id": "1",
            }
        ]
        labels = {
            "project": "demo",
            "model": "m1",
            "node_name": "AI Agent",
            "workflow": "Demo",
            "workflow_id": "wf-1",
        }

        new1, window1 = update_from_traces("demo", rows)
        self.assertEqual(new1, 1)
        self.assertEqual(window1, 1)
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_traces_total", labels), 1.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_ttft_ms_last", labels), 1000.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_trace_tokens_input_total", labels
            ),
            10.0,
        )

        # Second scrape with same trace id must not double-count counters
        new2, window2 = update_from_traces("demo", rows)
        self.assertEqual(new2, 0)
        self.assertEqual(window2, 1)
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_traces_total", labels), 1.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_ttft_ms_avg_window", labels),
            1000.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_window_traces", labels), 1.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_trace_ttft_ms",
                {
                    "project": "demo",
                    "execution_id": "1",
                    "model": "m1",
                    "node_name": "AI Agent",
                    "workflow": "Demo",
                    "workflow_id": "wf-1",
                    "trace_id": "t1",
                },
            ),
            1000.0,
        )


if __name__ == "__main__":
    unittest.main()
