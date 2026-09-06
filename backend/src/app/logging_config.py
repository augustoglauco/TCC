import json
import logging
from contextvars import ContextVar

conversation_id_ctx: ContextVar[str | None] = ContextVar("conversation_id", default=None)


class ConversationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.conversation_id = conversation_id_ctx.get()
        return True


_BASE_FIELDS = frozenset({"level", "logger", "message", "conversation_id", "exc_info"})


class JsonFormatter(logging.Formatter):
    """Formatter JSON com merge de campos estruturados do roteador.

    Campos extras entram via `logger.info("evento", extra={"router": {...}})`
    e são mesclados no topo do payload — não aninhados nem re-serializados —
    para que `domain`, `backend_escolhido`, `custo_estimado_usd` etc. sejam
    consultáveis direto no log (metodologia de docs/EVALUATION.md).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "conversation_id": getattr(record, "conversation_id", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        extra = getattr(record, "router", None)
        if isinstance(extra, dict):
            # Campos-base vencem em caso de colisão: um extra malformado não
            # pode mascarar level/message nem derrubar o log.
            payload.update({k: v for k, v in extra.items() if k not in _BASE_FIELDS})

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ConversationIdFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)
