"""Small, explicit SQLite migrations for schema changes not handled by create_all."""

from sqlalchemy import Engine, inspect, text


_TENANT_TABLES = (
    "ginasios",
    "planos",
    "clientes",
    "credenciais",
    "presencas",
    "contas_admin",
)


def migrar_empresas(engine: Engine) -> None:
    """Add tenant ownership and group pre-existing rows into one legacy company."""
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            with connection.begin():
                tabelas = set(inspect(connection).get_table_names())
                for tabela in _TENANT_TABLES:
                    if tabela not in tabelas:
                        continue
                    colunas = {coluna["name"] for coluna in inspect(connection).get_columns(tabela)}
                    if "empresa_id" not in colunas:
                        connection.exec_driver_sql(
                            f'ALTER TABLE "{tabela}" ADD COLUMN empresa_id VARCHAR(80)'
                        )

                if "empresas" in tabelas:
                    tem_dados_antigos = any(
                        connection.scalar(text(f'SELECT EXISTS(SELECT 1 FROM "{tabela}")'))
                        for tabela in ("ginasios", "planos", "clientes", "contas_admin")
                        if tabela in tabelas
                    )
                    if tem_dados_antigos:
                        connection.execute(
                            text(
                                "INSERT OR IGNORE INTO empresas "
                                "(id, nome, email, telefone, endereco) "
                                "VALUES (:id, :nome, :email, :telefone, :endereco)"
                            ),
                            {
                                "id": "empresa-legada",
                                "nome": "Empresa migrada",
                                "email": "admin@empresa-legada.local",
                                "telefone": "",
                                "endereco": "",
                            },
                        )
                        for tabela in ("ginasios", "planos", "clientes", "contas_admin"):
                            if tabela in tabelas:
                                connection.exec_driver_sql(
                                    f'UPDATE "{tabela}" SET empresa_id = \'empresa-legada\' '
                                    "WHERE empresa_id IS NULL"
                                )
                        if "credenciais" in tabelas and "clientes" in tabelas:
                            connection.exec_driver_sql(
                                "UPDATE credenciais SET empresa_id = "
                                "(SELECT clientes.empresa_id FROM clientes "
                                "WHERE clientes.id = credenciais.cliente_id) "
                                "WHERE empresa_id IS NULL"
                            )
                        if "presencas" in tabelas and "ginasios" in tabelas:
                            connection.exec_driver_sql(
                                "UPDATE presencas SET empresa_id = "
                                "(SELECT ginasios.empresa_id FROM ginasios "
                                "WHERE ginasios.id = presencas.ginasio_id) "
                                "WHERE empresa_id IS NULL"
                            )

                if "clientes" in tabelas:
                    connection.exec_driver_sql("DROP INDEX IF EXISTS ix_clientes_email")
                    connection.exec_driver_sql(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clientes_empresa_email "
                        "ON clientes (empresa_id, email)"
                    )
                if "credenciais" in tabelas:
                    _migrar_unicidade_credenciais(connection)
                    connection.exec_driver_sql(
                        "CREATE INDEX IF NOT EXISTS ix_credenciais_cliente_id "
                        "ON credenciais (cliente_id)"
                    )
                for tabela in _TENANT_TABLES:
                    if tabela in tabelas:
                        connection.exec_driver_sql(
                            f'CREATE INDEX IF NOT EXISTS "ix_{tabela}_empresa_id" '
                            f'ON "{tabela}" (empresa_id)'
                        )
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


def _migrar_unicidade_credenciais(connection) -> None:
    """Replace the old global credential uniqueness constraint with tenant scope."""
    constraints = inspect(connection).get_unique_constraints("credenciais")
    por_colunas = {
        tuple(constraint["column_names"])
        for constraint in constraints
    }
    if ("empresa_id", "metodo", "codigo") in por_colunas:
        return

    connection.exec_driver_sql("ALTER TABLE credenciais RENAME TO credenciais_antigas")
    connection.exec_driver_sql(
        "CREATE TABLE credenciais ("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, "
        "cliente_id VARCHAR(80) NOT NULL REFERENCES clientes(id) ON DELETE CASCADE, "
        "empresa_id VARCHAR(80) NOT NULL REFERENCES empresas(id), "
        "metodo VARCHAR(20) NOT NULL, "
        "codigo VARCHAR(250) NOT NULL, "
        "CONSTRAINT uq_credencial_empresa_metodo_codigo "
        "UNIQUE (empresa_id, metodo, codigo))"
    )
    connection.exec_driver_sql(
        "INSERT INTO credenciais (id, cliente_id, empresa_id, metodo, codigo) "
        "SELECT antiga.id, antiga.cliente_id, clientes.empresa_id, "
        "antiga.metodo, antiga.codigo "
        "FROM credenciais_antigas AS antiga "
        "JOIN clientes ON clientes.id = antiga.cliente_id"
    )
    connection.exec_driver_sql("DROP TABLE credenciais_antigas")
