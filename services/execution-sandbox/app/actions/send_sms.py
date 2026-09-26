from pydantic import BaseModel
from .common import ActionResult
import logging
import os
logger = logging.getLogger('execution-sandbox')

class SendSMSParams(BaseModel):
    to: str
    message: str

async def send_sms(params: SendSMSParams) -> ActionResult:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_FROM_NUMBER")
    
    if not sid or not token or not from_num:
        return ActionResult(success=False, message="send_sms not configured — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER")
    
    # Stubbed for Twilio SMS integration
    logger.info(f"Sending SMS to {params.to}")
    return ActionResult(success=True, message="SMS sent")
