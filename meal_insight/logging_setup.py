"""Journalisation avec masquage automatique des secrets."""
import logging
import re

from . import config

_PATTERNS = [
    (re.compile(r"(ApiKey\s+)\S+", re.I), r"\1***"),
    (re.compile(r"((?:api[_-]?key|password|passwd|token|secret)\s*[=:]\s*)\S+", re.I), r"\1***"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, repl in _PATTERNS:
            msg = pattern.sub(repl, msg)
        record.msg, record.args = msg, ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_meal_configured", False):
        return
    config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.setLevel(level)
    root._meal_configured = True  # type: ignore[attr-defined]
