from pydantic import BaseModel
from datetime import datetime
from ..registry import ActionResult
import logging
logger = logging.getLogger('execution-sandbox')

class CreateCalendarEventParams(BaseModel):
    title: str
    start_time: datetime
    duration_minutes: int = 30
    description: str = ""

async def create_calendar_event(params: CreateCalendarEventParams) -> ActionResult:
    # Stubbed for Google Calendar integration
    logger.info(f"Creating calendar event: {params.title}")
    return ActionResult(success=True, output="Event created")
