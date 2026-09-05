import json
import logging
from contextvars import ContextVar

conversation_id_ctx: ContextVar[str | None] = ContextVar("conversation_id", default=None)


class ConversationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.conversation_id = conversation_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "conversation_id": getattr(record, "conversation_id", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ConversationIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
