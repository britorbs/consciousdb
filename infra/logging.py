from __future__ import annotations
import logging
import json
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Include request_id if present in extra
        if hasattr(record, "request_id"):
            payload["request_id"] = getattr(record, "request_id")
        # Attach any extra (non standard) attributes added via LoggerAdapter
        for k, v in getattr(record, "__dict__", {}).items():
            if k not in payload and k not in ("args", "msg", "levelname", "levelno", "created", "msecs", "relativeCreated", "name", "message", "exc_info", "exc_text", "stack_info", "lineno", "pathname", "filename", "module", "funcName", "thread", "threadName", "process", "processName"):
                if not k.startswith("_"):
                    payload[k] = v
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)


def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    # Avoid duplicate handlers if re-invoked (tests)
    if not root.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger("consciousdb")
