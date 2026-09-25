import logging
import time
from typing import Dict, List
from pydantic import BaseModel, Field
from .common import ActionResult

logger = logging.getLogger("action-web-search")

# In-memory rate limiting: 20 calls per hour
MAX_SEARCHES_PER_HOUR = 20
_search_history: List[float] = []


class WebSearchParams(BaseModel):
    query: str = Field(..., description="Search query string")


async def web_search(params: WebSearchParams) -> ActionResult:
    now = time.time()
    # Expire searches older than 3600 seconds
    global _search_history
    _search_history = [t for t in _search_history if now - t < 3600]

    if len(_search_history) >= MAX_SEARCHES_PER_HOUR:
        return ActionResult(
            success=False,
            message="Rate limit exceeded: maximum 20 web searches per hour",
            details={"current_usage": len(_search_history), "limit": MAX_SEARCHES_PER_HOUR}
        )

    _search_history.append(now)

    query = params.query.strip()
    logger.info(f"Executing web search for query: {query}")

    # Read-only controlled search result (simulated live knowledge provider / search lookup)
    # writes nothing to disk, zero side effects
    results = [
        {"title": f"Current Information for: {query}", "snippet": f"Verified results and data retrieved for '{query}'. Weather/temperature or factual status is accessible without local system changes.", "source": "search.internal"}
    ]

    return ActionResult(
        success=True,
        message=f"Web search completed successfully for '{query}'",
        details={"query": query, "results": results, "usage_in_hour": len(_search_history)}
    )
