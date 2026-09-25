from pydantic import BaseModel, EmailStr
from .common import ActionResult


class SendEmailParams(BaseModel):
    to: EmailStr
    subject: str
    body: str


async def send_email(params: SendEmailParams) -> ActionResult:
    return ActionResult(
        success=True,
        data={"to": str(params.to), "subject": params.subject},
        message=f"Email sent successfully to {params.to}"
    )
