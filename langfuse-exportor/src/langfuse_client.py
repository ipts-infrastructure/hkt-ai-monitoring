from datetime import datetime, timedelta, timezone

import requests


class LangfuseClient:
    def __init__(self, host: str, public_key: str, secret_key: str):
        self._session = requests.Session()
        self._session.auth = (public_key, secret_key)
        self._session.headers["Accept"] = "application/json"
        self._base = host

    def fetch_daily_metrics(self, lookback_days: int) -> list[dict]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)
        params = {
            "fromTimestamp": start.isoformat().replace("+00:00", "Z"),
            "toTimestamp": end.isoformat().replace("+00:00", "Z"),
            "limit": lookback_days + 1,
        }
        response = self._session.get(
            f"{self._base}/api/public/metrics/daily",
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])
