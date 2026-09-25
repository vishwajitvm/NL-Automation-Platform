from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# Define custom TRACE log level (level 5, below DEBUG=10)
TRACE_LEVEL_NUM = 5
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")


def _logger_trace(self, message: Any, *args: Any, **kwargs: Any) -> None:
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kwargs)


logging.Logger.trace = _logger_trace  # type: ignore

# Register TRACE in TraceNest config if available
try:
    import tracenest.core.config as tn_cfg
    tn_cfg.LOG_LEVELS["TRACE"] = 5
except Exception:
    pass

logger = logging.getLogger("nl_automation")


class TraceNestLoggingHandler(logging.Handler):
    """
    Bridges all Python stdlib logging calls (DEBUG, TRACE, INFO, WARNING, ERROR, CRITICAL)
    directly into TraceNest logger with rich dynamic metadata.
    """
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
        self.setLevel(TRACE_LEVEL_NUM)

    def emit(self, record: logging.LogRecord) -> None:
        # Prevent recursion if record originates from TraceNest internals
        if record.name.startswith("tracenest"):
            return

        try:
            from tracenest import logger as tn_logger

            msg = record.getMessage()
            level = record.levelname

            meta: Dict[str, Any] = {
                "service": self.service_name,
                "logger": record.name,
                "module": record.module,
                "func": record.funcName,
                "line": record.lineno,
                "process": record.process,
                "thread": record.threadName,
            }

            # Capture extra metadata passed in log call
            if hasattr(record, "metadata") and isinstance(record.metadata, dict):
                meta.update(record.metadata)
            if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
                meta.update(record.extra_data)

            exc = record.exc_info[1] if record.exc_info else None

            tn_logger.log(
                level=level,
                message=msg,
                metadata=meta,
                exception=exc,
                exc_info=bool(record.exc_info),
            )
        except Exception:
            # Logging handler must never raise
            pass


def _start_log_symlink_aggregator(service_name: str) -> None:
    """
    For API gateway container: scans /app/TraceNestLogs_services/<service>/ and creates
    symlinks in /app/TraceNestLogs/{service}_{filename} so TraceNest UI lists and displays
    logs across all microservices.
    """
    if service_name != "api-gateway":
        return

    services_dir = Path("/app/TraceNestLogs_services")
    target_dir = Path.cwd() / "TraceNestLogs"
    target_dir.mkdir(parents=True, exist_ok=True)

    def _sync_loop():
        while True:
            try:
                if services_dir.exists():
                    for svc_path in services_dir.iterdir():
                        if svc_path.is_dir():
                            svc_name = svc_path.name
                            for log_file in svc_path.glob("*.log"):
                                dest_link = target_dir / f"{svc_name}_{log_file.name}"
                                if not dest_link.exists() and not dest_link.is_symlink():
                                    try:
                                        dest_link.symlink_to(log_file)
                                    except Exception:
                                        pass
            except Exception:
                pass
            time.sleep(2.0)

    t = threading.Thread(target=_sync_loop, daemon=True, name="TraceNestLogAggregator")
    t.start()


def setup_logging_and_middleware(app: FastAPI, service_name: str):
    """
    Configures TraceNest logging SDK and FastAPI UI route:
    1. Installs TraceNestLoggingHandler on root logger so all log calls (trace, debug, info, warn, error, critical)
       from anywhere in the application flow directly to TraceNest with rich metadata.
    2. Installs TraceNestMiddleware for automatic HTTP request/response metrics.
    3. Mounts the TraceNest dashboard UI router at /tracenest/ and redirects /tracenest -> /tracenest/.
    4. For API Gateway, aggregates log files from sibling services.
    """
    os.makedirs("TraceNestLogs", exist_ok=True)

    # 1. Configure stdlib root logger
    root_logger = logging.getLogger()
    log_level_name = os.getenv("LOG_LEVEL", "DEBUG").upper()
    resolved_level = getattr(logging, log_level_name, logging.DEBUG)
    root_logger.setLevel(resolved_level)

    # Ensure stdout stream handler exists with detailed formatter
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, TraceNestLoggingHandler)
        for h in root_logger.handlers
    )
    if not has_stream_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(resolved_level)
        formatter = logging.Formatter(
            f"%(asctime)s [%(levelname)s] [{service_name}:%(name)s:%(funcName)s:%(lineno)d] %(message)s"
        )
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 2. Attach TraceNestLoggingHandler to root logger
    has_tracenest_handler = any(
        isinstance(h, TraceNestLoggingHandler) for h in root_logger.handlers
    )
    if not has_tracenest_handler:
        tn_handler = TraceNestLoggingHandler(service_name)
        root_logger.addHandler(tn_handler)

    # 3. Attach TraceNestMiddleware
    try:
        from tracenest.fastapi.middleware import TraceNestMiddleware
        app.add_middleware(TraceNestMiddleware)
    except Exception as exc:
        logger.warning(f"TraceNestMiddleware unavailable for {service_name}: {exc}")

    # 4. Mount TraceNest UI Router & Redirect
    try:
        from tracenest.ui.router import router as tracenest_ui_router
        app.include_router(tracenest_ui_router)

        @app.get("/tracenest", include_in_schema=False)
        def tracenest_redirect():
            return RedirectResponse(url="/tracenest/", status_code=307)

        logger.info(f"TraceNest UI dashboard registered at /tracenest/ for {service_name}")
    except Exception as exc:
        logger.warning(f"TraceNest UI router could not be mounted for {service_name}: {exc}")

    # 5. Start aggregator if api-gateway
    _start_log_symlink_aggregator(service_name)

    logger.info(
        f"TraceNest SDK fully active for {service_name} at log level {log_level_name}."
    )
