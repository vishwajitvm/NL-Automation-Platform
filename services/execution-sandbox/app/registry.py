from typing import Any, Callable, Dict, List, Tuple, Type
from pydantic import BaseModel, ValidationError

from .actions.common import ActionResult, ActionNotRegisteredError, ActionNotAvailableError
from .actions.send_email import SendEmailParams, send_email
from .actions.send_webhook import SendWebhookParams, send_webhook
from .actions.write_log_notification import WriteLogParams, write_log_notification
from .actions.run_http_healthcheck import HealthcheckParams, run_http_healthcheck
from .actions.empty_recycle_bin import EmptyRecycleBinParams, empty_recycle_bin

REGISTRY: Dict[str, Tuple[Type[BaseModel], Callable]] = {
    "send_email": (SendEmailParams, send_email),
    "send_webhook": (SendWebhookParams, send_webhook),
    "write_log_notification": (WriteLogParams, write_log_notification),
    "run_http_healthcheck": (HealthcheckParams, run_http_healthcheck),
    "empty_recycle_bin": (EmptyRecycleBinParams, empty_recycle_bin),
}

ACTION_DESCRIPTIONS: Dict[str, str] = {
    "send_email": "Dispatches an email notification to a specified recipient with subject and body.",
    "send_webhook": "Sends an HTTP webhook payload to a designated URL.",
    "write_log_notification": "Records an application log notification at info, warning, or error level.",
    "run_http_healthcheck": "Checks the HTTP response status of a target endpoint against expected status code.",
    "empty_recycle_bin": "Triggers Recycle Bin cleanup (Host-boundary action, requires host agent).",
}


def get_mcp_tools() -> List[Dict[str, Any]]:
    tools = []
    for name, (schema, _) in REGISTRY.items():
        tools.append({
            "name": name,
            "description": ACTION_DESCRIPTIONS.get(name, f"Executes {name} action"),
            "inputSchema": schema.model_json_schema()
        })
    return tools


async def invoke(action_name: str, raw_params: Dict[str, Any]) -> ActionResult:
    if action_name not in REGISTRY:
        raise ActionNotRegisteredError(action_name)
    schema, fn = REGISTRY[action_name]
    # Pydantic validation error will raise ValidationError -> handled as 400
    validated = schema(**raw_params)
    return await fn(validated)
