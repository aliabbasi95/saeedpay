# saeedpay/logging.py

import contextvars
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)

_SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "api_key",
    "password",
    "otp",
    "otp_code",
    "phone_number",
    "national_id",
    "cas_code",
    "login_token",
}


def set_request_id(request_id: str):
    return _request_id_ctx.set(request_id)


def reset_request_id(token):
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def mask_phone_number(value: str | None) -> str | None:
    if not value:
        return value

    raw = str(value)
    if len(raw) <= 4:
        return "*" * len(raw)

    return f"{'*' * (len(raw) - 4)}{raw[-4:]}"


def sanitize_log_value(value: Any, key: str | None = None) -> Any:
    if key in _SENSITIVE_KEYS:
        if key == "phone_number":
            return mask_phone_number(str(value))
        return "***"

    if isinstance(value, dict):
        return {str(k): sanitize_log_value(v, key=str(k)) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_value(item) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return value


def build_log_payload(
    *,
    event: str,
    module: str | None = None,
    action: str | None = None,
    **context,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": event,
        "request_id": get_request_id(),
    }

    if module:
        payload["module"] = module

    if action:
        payload["action"] = action

    for key, value in context.items():
        payload[key] = sanitize_log_value(value, key=key)

    return payload


def log_event(
    logger: logging.Logger,
    *,
    level: int | str,
    event: str,
    message: str | None = None,
    module: str | None = None,
    action: str | None = None,
    **context,
):
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    payload = build_log_payload(
        event=event,
        module=module,
        action=action,
        **context,
    )

    logger.log(
        level,
        message or event,
        extra={"structured": payload},
    )


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        structured = getattr(record, "structured", None)
        if isinstance(structured, dict):
            payload.update(structured)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class KeyValueLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, self.datefmt)} "
            f"{record.levelname} "
            f"{record.name} "
            f"{record.getMessage()}"
        )

        structured = getattr(record, "structured", None)
        if not isinstance(structured, dict):
            if record.exc_info:
                return f"{base}\n{self.formatException(record.exc_info)}"
            return base

        extra_parts = []
        for key, value in structured.items():
            if value is None:
                continue
            extra_parts.append(f"{key}={value}")

        rendered = base
        if extra_parts:
            rendered = f"{base} | " + " ".join(extra_parts)

        if record.exc_info:
            rendered = f"{rendered}\n{self.formatException(record.exc_info)}"

        return rendered
