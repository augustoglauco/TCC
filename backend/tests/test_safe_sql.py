import pytest
from app.services.safe_sql import (
    SQLSecurityError,
    execute_readonly_sql,
    get_catalog_schema_prompt,
    validate_readonly_sql,
)


def test_validate_readonly_sql_valid():
    valid_query = "SELECT nome, preco FROM produtos ORDER BY preco DESC LIMIT 10"
    cleaned = validate_readonly_sql(valid_query)
    assert cleaned.startswith("SELECT")
    assert "LIMIT" in cleaned


def test_validate_readonly_sql_blocks_multiple_statements():
    with pytest.raises(SQLSecurityError, match="Múltiplas instruções"):
        validate_readonly_sql("SELECT 1; DROP TABLE produtos")


def test_validate_readonly_sql_blocks_destructive_keywords():
    with pytest.raises(SQLSecurityError, match="Comando não permitido"):
        validate_readonly_sql("INSERT INTO produtos (nome) VALUES ('hack')")

    with pytest.raises(SQLSecurityError, match="Comando não permitido"):
        validate_readonly_sql("DELETE FROM produtos WHERE id = 1")

    with pytest.raises(SQLSecurityError, match="Comando não permitido"):
        validate_readonly_sql("UPDATE produtos SET preco = 0")

    with pytest.raises(SQLSecurityError, match="Comando não permitido"):
        validate_readonly_sql("DROP TABLE clientes")

    with pytest.raises(SQLSecurityError, match="Comando não permitido"):
        validate_readonly_sql("TRUNCATE TABLE produtos")


def test_validate_readonly_sql_enforces_limit():
    query = "SELECT categoria, COUNT(*) FROM produtos GROUP BY categoria"
    cleaned = validate_readonly_sql(query)
    assert "LIMIT 50" in cleaned


def test_get_catalog_schema_prompt():
    prompt = get_catalog_schema_prompt()
    assert "produtos" in prompt
    assert "cliente_compras" in prompt
    assert "pedidos" in prompt
    assert "pedido_itens" in prompt


@pytest.mark.asyncio
async def test_execute_readonly_sql_success(db_session):
    from decimal import Decimal
    from app.db.models import Produto

    p = Produto(nome="Produto Teste Seguro", descricao="Desc", preco=Decimal("99.90"), categoria="Segurança")
    db_session.add(p)
    await db_session.commit()

    rows = await execute_readonly_sql(db_session, "SELECT nome, preco, categoria FROM produtos WHERE nome = 'Produto Teste Seguro'")
    assert len(rows) == 1
    assert rows[0]["nome"] == "Produto Teste Seguro"
    assert float(rows[0]["preco"]) == 99.90
    assert rows[0]["categoria"] == "Segurança"
