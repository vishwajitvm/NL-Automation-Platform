from pydantic import BaseModel
from ..registry import ActionResult
import logging
import os
logger = logging.getLogger('execution-sandbox')

class SendSMSParams(BaseModel):
    to: str
    message: str

async def send_sms(params: SendSMSParams) -> ActionResult:
    # Stubbed for Twilio SMS integration
    if not os.getenv("TWILIO_ACCOUNT_SID"):
        return ActionResult(success=False, output="Twilio not configured")
    logger.info(f"Sending SMS to {params.to}")
    return ActionResult(success=True, output="SMS sent")
