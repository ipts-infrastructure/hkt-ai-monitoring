import unittest
from unittest.mock import patch

from prometheus_client import REGISTRY

from metrics import (
    DAILY_TRACES,
    TOKENS_TOTAL,
    clear_gauges,
    update_from_daily_rows,
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


if __name__ == "__main__":
    unittest.main()
