"""Schema inicial do Gym Presence."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ginasios",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("endereco", sa.String(length=300), nullable=False),
    )
    op.create_table(
        "planos",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("descricao", sa.String(length=1000), nullable=False),
        sa.Column("max_visitas_semana", sa.Integer()),
        sa.Column("max_visitas_mes", sa.Integer()),
        sa.Column("hora_inicio", sa.Time()),
        sa.Column("hora_fim", sa.Time()),
        sa.Column("dias_semana", sa.JSON(), nullable=False),
        sa.Column("duracao_maxima_minutos", sa.Integer()),
        sa.Column("ginasios_permitidos", sa.JSON(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "clientes",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("telefone", sa.String(length=80), nullable=False),
        sa.Column("plano_id", sa.String(length=80), nullable=False),
        sa.Column("assinatura_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assinatura_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["plano_id"], ["planos.id"]),
    )
    op.create_index("ix_clientes_email", "clientes", ["email"], unique=True)
    op.create_table(
        "contas_admin",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contas_admin_email", "contas_admin", ["email"], unique=True)
    op.create_table(
        "credenciais",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("cliente_id", sa.String(length=80), nullable=False),
        sa.Column("metodo", sa.String(length=20), nullable=False),
        sa.Column("codigo", sa.String(length=250), nullable=False),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("metodo", "codigo", name="uq_credencial_metodo_codigo"),
    )
    op.create_index("ix_credenciais_cliente_id", "credenciais", ["cliente_id"])
    op.create_table(
        "presencas",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("cliente_id", sa.String(length=80), nullable=False),
        sa.Column("ginasio_id", sa.String(length=80), nullable=False),
        sa.Column("metodo", sa.String(length=20), nullable=False),
        sa.Column("entrada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saida_em", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.ForeignKeyConstraint(["ginasio_id"], ["ginasios.id"]),
    )
    op.create_index(
        "ix_presencas_cliente_entrada",
        "presencas",
        ["cliente_id", "entrada_em"],
    )


def downgrade() -> None:
    op.drop_table("presencas")
    op.drop_index("ix_credenciais_cliente_id", table_name="credenciais")
    op.drop_table("credenciais")
    op.drop_index("ix_contas_admin_email", table_name="contas_admin")
    op.drop_table("contas_admin")
    op.drop_index("ix_clientes_email", table_name="clientes")
    op.drop_table("clientes")
    op.drop_table("planos")
    op.drop_table("ginasios")