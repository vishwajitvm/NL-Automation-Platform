import logging
import os
from fastapi import FastAPI
from shared.redaction import redact_data

logger = logging.getLogger("nl_automation")

def setup_logging_and_middleware(app: FastAPI, service_name: str):
    """
    Configures TraceNestMiddleware with secret redaction,
    falling back to Python standard logging if TraceNest encounters an issue.
    """
    os.makedirs("TraceNestLogs", exist_ok=True)
    
    # Configure stdlib logging fallback
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s [%(levelname)s] [{service_name}] %(message)s"
    )
    
    try:
        try:
            from tracenest.fastapi import TraceNestMiddleware
        except ImportError:
            from tracenest.fastapi.middleware import TraceNestMiddleware
            
        app.add_middleware(TraceNestMiddleware)
        logger.info(f"TraceNestMiddleware enabled for {service_name}")
    except Exception as exc:
        logger.warning(f"TraceNestMiddleware unavailable for {service_name}: {exc}. Fallback to stdlib logging.")
