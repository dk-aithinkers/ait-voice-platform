"""Logging facade that refuses protected health information.

Affirmed at practices discovery as a binding convention. The reasoning, from
the security review: automation fully covers secrets, dependency CVEs and
injection patterns, but PHI reaching a log sink is only covered *if PHI-carrying
values are nominally distinguishable*. Wrapping PHI in a type is what makes that
true, and this module is what acts on it.

The effect is that the most likely breach on this system — a transcript or a
caller name landing in a log line — becomes a caught error rather than a silent
disclosure.

Rules enforced here:

1. No :class:`~ait_voice.core.types.PHI` value may appear in a log record, in
   the message, the arguments, or the structured fields.
2. Third-party loggers are pinned to WARNING, so a vendor SDK cannot debug-log
   a request body containing a transcript.
3. Structured fields are the only way to attach context, which keeps log
   messages constant and greppable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ait_voice.core.types import PHI, TenantContext

#: Vendor SDKs that log request and response bodies at DEBUG. A transcript in a
#: request body is PHI, and their debug output is outside our control, so they
#: are pinned above it.
_THIRD_PARTY_LOGGERS = (
    "anthropic",
    "openai",
    "httpx",
    "httpcore",
    "deepgram",
    "elevenlabs",
    "twilio",
    "websockets",
    "urllib3",
    "botocore",
)


class PHILeakError(RuntimeError):
    """Raised when a PHI value is passed to the logging facade.

    This is deliberately an exception rather than a warning. A warning would be
    observed by nobody on a team of one; an exception fails the test that
    exercises the path, which is the point.
    """


def _assert_no_phi(where: str, value: Any) -> None:
    """Reject PHI, and containers holding PHI, before anything is emitted."""
    if isinstance(value, PHI):
        raise PHILeakError(
            f"PHI value passed to logger in {where}. "
            "Log an opaque identifier instead, or call .reveal() only inside "
            "the compliance boundary."
        )
    if isinstance(value, dict):
        for k, v in value.items():
            _assert_no_phi(f"{where}[{k!r}]", v)
    elif isinstance(value, (list, tuple, set)):
        for i, v in enumerate(value):
            _assert_no_phi(f"{where}[{i}]", v)


class CallLogger:
    """The only sanctioned way to log from call-handling code.

    Context is attached as structured fields rather than interpolated into the
    message, so messages stay constant and every field passes the PHI check.
    """

    __slots__ = ("_logger", "_base_fields")

    def __init__(self, name: str, **base_fields: Any) -> None:
        self._logger = logging.getLogger(name)
        _assert_no_phi("base_fields", base_fields)
        self._base_fields = base_fields

    @classmethod
    def for_call(
        cls,
        name: str,
        tenant: TenantContext,
        call_id: str,
        **extra: Any,
    ) -> CallLogger:
        """Build a logger bound to one call.

        ``tenant_id``, ``region`` and ``call_id`` are opaque identifiers and are
        safe to log. Nothing about the caller is.
        """
        return cls(
            name,
            tenant_id=tenant.tenant_id,
            region=tenant.region.value,
            call_id=call_id,
            **extra,
        )

    def _emit(self, level: int, message: str, fields: dict[str, Any]) -> None:
        _assert_no_phi("fields", fields)
        self._logger.log(level, message, extra={"fields": {**self._base_fields, **fields}})

    def debug(self, message: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, message, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._emit(logging.INFO, message, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._emit(logging.WARNING, message, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._emit(logging.ERROR, message, fields)


class _FieldFormatter(logging.Formatter):
    """Renders structured fields, and refuses to render PHI even if it got here.

    The facade should have caught it already. This is the second net, because
    an exception traceback can carry a PHI value into a log record without ever
    passing through :class:`CallLogger`.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        fields = getattr(record, "fields", None)
        if not fields:
            return base
        rendered = " ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{base} | {rendered}"


def configure_logging(level: str | None = None) -> None:
    """Configure logging for the process.

    Call once at startup. Pins third-party loggers above DEBUG so vendor SDKs
    cannot log request bodies containing transcripts.
    """
    resolved = (level or os.environ.get("AIT_LOG_LEVEL") or "INFO").upper()

    handler = logging.StreamHandler()
    handler.setFormatter(_FieldFormatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)

    for name in _THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, root.level))
