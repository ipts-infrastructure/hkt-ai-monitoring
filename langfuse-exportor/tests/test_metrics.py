import unittest
from unittest.mock import patch

from prometheus_client import REGISTRY

from langfuse_client import extract_observation_metrics, extract_trace_metrics
from metrics import (
    clear_daily_gauges,
    clear_gauges,
    update_from_daily_rows,
    update_from_observations,
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


class ExtractObservationMetricsTest(unittest.TestCase):
    def test_extracts_langfuse_ttft_tps_and_usage(self) -> None:
        extracted = extract_observation_metrics(
            {
                "id": "obs-1",
                "traceId": "tr-1",
                "type": "GENERATION",
                "name": "OpenAI Chat Model",
                "providedModelName": "qwen/qwen3.6-27b",
                "timeToFirstToken": 1.1026,  # seconds
                "tokensPerSecond": 42.5,
                "latency": 3.5,
                "usageDetails": {"input": 33, "output": 156, "total": 189},
                "metadata": {
                    "n8n_node_name": "AI Agent",
                    "n8n_workflow_name": "Demo Agent TTFT Langfuse",
                    "n8n_workflow_id": "wf-123",
                    "executionId": 660,
                },
            }
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertAlmostEqual(extracted["ttft_ms"], 1102.6)
        self.assertEqual(extracted["latency_ms"], 3500.0)
        self.assertEqual(extracted["tps"], 42.5)
        self.assertEqual(extracted["input_tokens"], 33.0)
        self.assertEqual(extracted["output_tokens"], 156.0)
        self.assertEqual(extracted["total_tokens"], 189.0)
        self.assertEqual(extracted["node_name"], "AI Agent")
        self.assertEqual(extracted["execution_id"], "660")
        self.assertEqual(extracted["observation_id"], "obs-1")
        self.assertEqual(extracted["trace_id"], "tr-1")

    def test_ignores_n8n_metadata_ttft(self) -> None:
        extracted = extract_observation_metrics(
            {
                "id": "obs-2",
                "traceId": "tr-2",
                "type": "GENERATION",
                "metadata": {
                    "AI_TTFT_Ms": 99999,
                    "inputTokens": 10,
                    "outputTokens": 20,
                },
                "usageDetails": {"input": 11, "output": 22, "total": 33},
                "timeToFirstToken": 0.5,
            }
        )
        assert extracted is not None
        # Must use Langfuse timeToFirstToken, not metadata AI_TTFT_Ms
        self.assertEqual(extracted["ttft_ms"], 500.0)
        self.assertEqual(extracted["input_tokens"], 11.0)
        self.assertEqual(extracted["output_tokens"], 22.0)

    def test_derives_tps_from_langfuse_latency_when_missing(self) -> None:
        extracted = extract_observation_metrics(
            {
                "id": "obs-3",
                "traceId": "tr-3",
                "type": "GENERATION",
                "timeToFirstToken": 0.2,
                "latency": 2.0,
                "outputUsage": 100,
                "inputUsage": 10,
                "totalUsage": 110,
            }
        )
        assert extracted is not None
        self.assertEqual(extracted["ttft_ms"], 200.0)
        self.assertEqual(extracted["latency_ms"], 2000.0)
        self.assertEqual(extracted["tps"], 50.0)

    def test_skips_without_langfuse_metrics(self) -> None:
        self.assertIsNone(
            extract_observation_metrics(
                {
                    "id": "x",
                    "type": "GENERATION",
                    "metadata": {"AI_TTFT_Ms": 100, "foo": "bar"},
                }
            )
        )

    def test_deprecated_trace_extractor_returns_none(self) -> None:
        self.assertIsNone(
            extract_trace_metrics(
                {
                    "id": "t",
                    "metadata": {"AI_TTFT_Ms": 100, "inputTokens": 1},
                }
            )
        )


class UpdateFromObservationsTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_daily_gauges()
        from metrics import _SEEN, _SEEN_SET

        _SEEN.clear()
        _SEEN_SET.clear()

    def test_increments_counters_and_ttft_once_per_observation(self) -> None:
        rows = [
            {
                "observation_id": "o1",
                "trace_id": "t1",
                "ttft_ms": 1000.0,
                "latency_ms": 2500.0,
                "tps": 25.0,
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

        new1, window1 = update_from_observations("demo", rows)
        self.assertEqual(new1, 1)
        self.assertEqual(window1, 1)
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_traces_total", labels), 1.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_ttft_ms_last", labels), 1000.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_tps_last", labels), 25.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_trace_tokens_input_total", labels
            ),
            10.0,
        )

        new2, window2 = update_from_observations("demo", rows)
        self.assertEqual(new2, 0)
        self.assertEqual(window2, 1)
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_traces_total", labels), 1.0
        )
        self.assertEqual(
            REGISTRY.get_sample_value("langfuse_tps_avg_window", labels), 25.0
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
                    "observation_id": "o1",
                },
            ),
            1000.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_trace_tps",
                {
                    "project": "demo",
                    "execution_id": "1",
                    "model": "m1",
                    "node_name": "AI Agent",
                    "workflow": "Demo",
                    "workflow_id": "wf-1",
                    "trace_id": "t1",
                    "observation_id": "o1",
                },
            ),
            25.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_trace_latency_ms",
                {
                    "project": "demo",
                    "execution_id": "1",
                    "model": "m1",
                    "node_name": "AI Agent",
                    "workflow": "Demo",
                    "workflow_id": "wf-1",
                    "trace_id": "t1",
                    "observation_id": "o1",
                },
            ),
            2500.0,
        )
        self.assertEqual(
            REGISTRY.get_sample_value(
                "langfuse_latency_ms_sum",
                {
                    "project": "demo",
                    "model": "m1",
                    "node_name": "AI Agent",
                    "workflow": "Demo",
                    "workflow_id": "wf-1",
                },
            ),
            2500.0,
        )


if __name__ == "__main__":
    unittest.main()
