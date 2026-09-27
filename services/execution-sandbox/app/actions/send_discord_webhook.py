from pydantic import BaseModel, HttpUrl, validator
from .common import ActionResult
import httpx
import logging
logger = logging.getLogger('execution-sandbox')

class DiscordWebhookParams(BaseModel):
    webhook_url: HttpUrl
    message: str

    @validator('webhook_url')
    def check_discord_host(cls, v):
        if not str(v).startswith('https://discord.com/api/webhooks/'):
            raise ValueError('Must be a valid discord.com webhook URL')
        return v

async def send_discord_webhook(params: DiscordWebhookParams) -> ActionResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(str(params.webhook_url), json={"content": params.message})
            if resp.status_code >= 400:
                return ActionResult(success=False, message=f"Failed: {resp.status_code}")
            return ActionResult(success=True, message="Message sent to Discord")
    except Exception as e:
        return ActionResult(success=False, message=str(e))
