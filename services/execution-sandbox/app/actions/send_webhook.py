from typing import Any, Dict, Literal
from pydantic import BaseModel, HttpUrl
import httpx
from .common import ActionResult


class SendWebhookParams(BaseModel):
    url: HttpUrl
    method: Literal["POST", "GET"] = "POST"
    payload: Dict[str, Any] = {}


async def send_webhook(params: SendWebhookParams) -> ActionResult:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if params.method == "POST":
                resp = await client.post(str(params.url), json=params.payload)
            else:
                resp = await client.get(str(params.url))
            return ActionResult(
                success=resp.is_success,
                data={"status_code": resp.status_code},
                message=f"Webhook executed with status {resp.status_code}"
            )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Webhook dispatch failed: {e}"
        )
