from app.rag.embedders_registry import EmbedderRegistry


def test_get_mesmo_modelo_duas_vezes_retorna_a_mesma_instancia():
    registry = EmbedderRegistry()

    a = registry.get("modelo-a")
    b = registry.get("modelo-a")

    assert a is b


def test_get_modelos_diferentes_retorna_instancias_diferentes():
    registry = EmbedderRegistry()

    a = registry.get("modelo-a")
    b = registry.get("modelo-b")

    assert a is not b
    assert a.model_name == "modelo-a"
    assert b.model_name == "modelo-b"
