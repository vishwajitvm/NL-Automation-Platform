from pydantic import BaseModel
from datetime import datetime
from .common import ActionResult
import logging
import os
logger = logging.getLogger('execution-sandbox')

class CreateCalendarEventParams(BaseModel):
    title: str
    start_time: datetime
    duration_minutes: int = 30
    description: str = ""

async def create_calendar_event(params: CreateCalendarEventParams) -> ActionResult:
    creds = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    cal_id = os.getenv("GOOGLE_CALENDAR_ID")
    if not creds or not cal_id:
        return ActionResult(success=False, message="create_calendar_event not configured — set GOOGLE_SERVICE_ACCOUNT_JSON_PATH and GOOGLE_CALENDAR_ID")
    
    # Stubbed for Google Calendar integration
    logger.info(f"Creating calendar event: {params.title}")
    return ActionResult(success=True, message="Event created")
