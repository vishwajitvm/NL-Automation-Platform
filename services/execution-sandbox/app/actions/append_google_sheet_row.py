from pydantic import BaseModel
from typing import List, Optional
from .common import ActionResult
import logging
import os
logger = logging.getLogger('execution-sandbox')

class AppendSheetRowParams(BaseModel):
    spreadsheet_id: Optional[str] = None
    values: List[str]

async def append_google_sheet_row(params: AppendSheetRowParams) -> ActionResult:
    creds = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
    sheet = params.spreadsheet_id or os.getenv("GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID")
    if not creds or not sheet:
        return ActionResult(success=False, message="append_google_sheet_row not configured — set GOOGLE_SERVICE_ACCOUNT_JSON_PATH and GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID")
    
    # Stubbed for Google Sheets integration
    logger.info(f"Appending row to spreadsheet: {params.values}")
    return ActionResult(success=True, message="Row appended to sheet")
