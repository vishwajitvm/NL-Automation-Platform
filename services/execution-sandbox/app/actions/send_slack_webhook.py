from pydantic import BaseModel, HttpUrl, validator
from .common import ActionResult
import httpx
import logging
logger = logging.getLogger('execution-sandbox')

class SlackWebhookParams(BaseModel):
    webhook_url: HttpUrl
    message: str

    @validator('webhook_url')
    def check_slack_host(cls, v):
        if not str(v).startswith('https://hooks.slack.com/'):
            raise ValueError('Must be a valid hooks.slack.com URL')
        return v

async def send_slack_webhook(params: SlackWebhookParams) -> ActionResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(str(params.webhook_url), json={"text": params.message})
            if resp.status_code >= 400:
                return ActionResult(success=False, message=f"Failed: {resp.status_code}")
            return ActionResult(success=True, message="Message sent to Slack")
    except Exception as e:
        return ActionResult(success=False, message=str(e))
