import logging
from typing import Dict

logger = logging.getLogger("trigger-engine")

# Container-reachable stand-in metrics for MVP
MOCK_METRICS: Dict[str, float] = {
    "recycle_bin_percentage": 50.0,
    "disk_usage_pct": 40.0,
}


def get_metric(metric_name: str) -> float:
    return MOCK_METRICS.get(metric_name, 0.0)


def set_metric(metric_name: str, value: float) -> None:
    MOCK_METRICS[metric_name] = float(value)
    logger.info(f"Mock metric '{metric_name}' set to {value}")
