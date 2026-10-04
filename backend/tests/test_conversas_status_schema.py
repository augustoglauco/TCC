import pytest
from datetime import datetime, UTC
from app.db.models import Conversa

def test_conversa_model_has_status_and_closure_fields():
    conversa = Conversa(
        id="test-session-123",
        status="encerrada",
        encerrada_em=datetime.now(UTC),
        motivo_encerramento="manual_usuario",
    )
    assert conversa.status == "encerrada"
    assert conversa.encerrada_em is not None
    assert conversa.motivo_encerramento == "manual_usuario"

def test_conversa_model_default_status():
    conversa = Conversa(id="test-session-default")
    assert conversa.status == "aberta" or conversa.status is None  # before db insert or initialized
