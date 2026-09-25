from pydantic import BaseModel, HttpUrl
import httpx
from .common import ActionResult


class HealthcheckParams(BaseModel):
    url: HttpUrl
    expected_status: int = 200


async def run_http_healthcheck(params: HealthcheckParams) -> ActionResult:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(str(params.url))
            success = (resp.status_code == params.expected_status)
            return ActionResult(
                success=success,
                data={"status_code": resp.status_code, "expected": params.expected_status},
                message=f"Healthcheck returned {resp.status_code} (expected {params.expected_status})"
            )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Healthcheck connection failed: {e}"
        )
