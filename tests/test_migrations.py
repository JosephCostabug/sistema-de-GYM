"""Testes de compatibilidade da migração dos dados antigos para empresas."""

from sqlalchemy import create_engine, inspect, text

from app.data.migrations import migrar_empresas


def test_migracao_legada_preserva_registros_e_aplica_unicidade_por_empresa():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE empresas ("
            "id VARCHAR(80) PRIMARY KEY, nome VARCHAR(160) NOT NULL, "
            "email VARCHAR(320) NOT NULL, telefone VARCHAR(80) NOT NULL, "
            "endereco VARCHAR(300) NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE ginasios ("
            "id VARCHAR(80) PRIMARY KEY, nome VARCHAR(160) NOT NULL, "
            "endereco VARCHAR(300) NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE planos (id VARCHAR(80) PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE clientes ("
            "id VARCHAR(80) PRIMARY KEY, plan_id VARCHAR(80) NOT NULL "
            "REFERENCES planos(id), email VARCHAR(320) NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX ix_clientes_email ON clientes (email)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE credenciais ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id VARCHAR(80) NOT NULL "
            "REFERENCES clientes(id) ON DELETE CASCADE, "
            "metodo VARCHAR(20) NOT NULL, codigo VARCHAR(250) NOT NULL, "
            "CONSTRAINT uq_credencial_metodo_codigo UNIQUE (metodo, codigo))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE presencas ("
            "id VARCHAR(80) PRIMARY KEY, cliente_id VARCHAR(80) NOT NULL "
            "REFERENCES clientes(id), ginasio_id VARCHAR(80) NOT NULL "
            "REFERENCES ginasios(id))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE contas_admin ("
            "id VARCHAR(80) PRIMARY KEY, email VARCHAR(320) NOT NULL, "
            "password_hash VARCHAR(256) NOT NULL, ativo BOOLEAN NOT NULL, "
            "criado_em DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO ginasios VALUES ('gym-antigo', 'Unidade antiga', '')"
        )
        connection.exec_driver_sql("INSERT INTO planos VALUES ('plano-antigo')")
        connection.exec_driver_sql(
            "INSERT INTO clientes VALUES "
            "('cli-antigo', 'plano-antigo', 'cliente@example.test')"
        )
        connection.exec_driver_sql(
            "INSERT INTO credenciais (cliente_id, metodo, codigo) "
            "VALUES ('cli-antigo', 'qr', 'QR-ANTIGO')"
        )
        connection.exec_driver_sql(
            "INSERT INTO presencas VALUES ('pres-antiga', 'cli-antigo', 'gym-antigo')"
        )
        connection.exec_driver_sql(
            "INSERT INTO contas_admin VALUES "
            "('adm-antigo', 'admin@example.test', 'hash', 1, '2026-01-01')"
        )

    migrar_empresas(engine)
    migrar_empresas(engine)

    with engine.begin() as connection:
        for tabela in ("ginasios", "planos", "clientes", "contas_admin"):
            empresa_id = connection.scalar(
                text(f'SELECT empresa_id FROM "{tabela}" LIMIT 1')
            )
            assert empresa_id == "empresa-legada"
        assert connection.scalar(
            text("SELECT empresa_id FROM credenciais WHERE codigo = 'QR-ANTIGO'")
        ) == "empresa-legada"
        assert connection.scalar(
            text("SELECT empresa_id FROM presencas WHERE id = 'pres-antiga'")
        ) == "empresa-legada"
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []

        connection.exec_driver_sql(
            "INSERT INTO empresas VALUES "
            "('emp-nova', 'Outra empresa', 'outra@example.test', '', '')"
        )
        connection.exec_driver_sql(
            "INSERT INTO planos (id, empresa_id) VALUES ('plano-novo', 'emp-nova')"
        )
        connection.exec_driver_sql(
            "INSERT INTO clientes (id, plan_id, email, empresa_id) "
            "VALUES ('cli-novo', 'plano-novo', 'cliente@example.test', 'emp-nova')"
        )
        connection.exec_driver_sql(
            "INSERT INTO credenciais (cliente_id, empresa_id, metodo, codigo) "
            "VALUES ('cli-novo', 'emp-nova', 'qr', 'QR-ANTIGO')"
        )

    constraints = inspect(engine).get_unique_constraints("credenciais")
    assert any(
        constraint["column_names"] == ["empresa_id", "metodo", "codigo"]
        for constraint in constraints
    )
    engine.dispose()
