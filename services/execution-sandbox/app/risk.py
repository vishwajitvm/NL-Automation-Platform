from typing import Literal

RiskTier = Literal["low", "medium", "high"]

RISK_TIERS: dict[str, RiskTier] = {
    # Low risk — read-only or low-blast-radius
    "web_search": "low",
    "check_disk_usage": "low",
    "list_drives": "low",
    "get_memory_usage": "low",
    "list_top_processes": "low",
    "list_connected_devices": "low",
    "run_http_healthcheck": "low",
    "write_log_notification": "low",
    "send_email": "low",
    "send_webhook": "low",
    "browser_open_url": "low",
    "browser_list_open_tabs": "low",
    "browser_close_tab": "low",

    # Medium risk — curated targets or trash
    "clean_temp_and_cache": "medium",
    "empty_trash": "medium",
    "empty_recycle_bin": "medium",
    "browser_clear_managed_cache": "medium",

    # High risk — arbitrary user-specified path deletion
    "delete_path": "high",
}


def get_risk_tier(action_name: str) -> RiskTier:
    """Fixed lookup table in code assigning risk tiers. Never self-rated by LLM."""
    return RISK_TIERS.get(action_name, "high")
