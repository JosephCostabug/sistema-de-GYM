from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.data.control_plane import EstadoProvisionamento, PlanoControlo
from app.data.tenant_databases import (
    ConflitoBaseEmpresa,
    GestorBasesEmpresa,
    GinasioEmpresaRecord,
)
from app.models.schemas import Empresa, Ginasio
from app.services.provisionamento import (
    ErroProvisionamento,
    provisionar_empresa,
)


def empresa(identificador: str) -> Empresa:
    return Empresa(
        id=identificador,
        nome=f"Empresa {identificador}",
        email=f"contacto+{identificador}@example.test",
    )


def ginasio(identificador: str) -> Ginasio:
    return Ginasio(id=f"gym-{identificador}", nome=f"Ginásio {identificador}")


@pytest.fixture
def infraestrutura(tmp_path: Path):
    controlo = PlanoControlo(f"sqlite:///{tmp_path / 'controlo.db'}")
    gestor = GestorBasesEmpresa(tmp_path / "empresas")
    controlo.inicializar()
    yield controlo, gestor, tmp_path
    controlo.engine.dispose()


def provisionar(
    controlo: PlanoControlo,
    gestor: GestorBasesEmpresa,
    identificador: str,
    email_admin: str | None = None,
):
    return provisionar_empresa(
        controlo=controlo,
        bases_empresa=gestor,
        empresa=empresa(identificador),
        administrador_id=f"adm-{identificador}",
        administrador_email=email_admin or f"{identificador}@example.test",
        password_hash="hash-de-teste",
        ginasio=ginasio(identificador),
    )


@contextmanager
def ligar_base(caminho: Path):
    engine = create_engine(f"sqlite:///{caminho}")

    @event.listens_for(engine, "connect")
    def ativar_chaves_estrangeiras(conexao, _registro):
        conexao.execute("PRAGMA foreign_keys = ON")

    try:
        yield engine
    finally:
        engine.dispose()


def test_provisionamento_cria_plano_de_controlo_e_base_isolada(infraestrutura):
    controlo, gestor, raiz = infraestrutura

    resultado = provisionar(controlo, gestor, "emp-a1")

    assert resultado.estado == EstadoProvisionamento.ATIVO
    assert resultado.versao_esquema == 2
    assert resultado.caminho_base_dados == raiz / "empresas" / "emp-a1.sqlite3"
    assert resultado.caminho_base_dados.is_file()
    empresa_controle = controlo.obter_empresa("emp-a1")
    assert empresa_controle is not None
    assert empresa_controle.estado == EstadoProvisionamento.ATIVO
    assert empresa_controle.chave_base_dados == "emp-a1"
    assert controlo.obter_administrador("adm-emp-a1").email == "emp-a1@example.test"

    with ligar_base(resultado.caminho_base_dados) as engine:
        tabelas_empresa = set(inspect(engine).get_table_names())
    assert tabelas_empresa == {
        "assinaturas",
        "auditoria",
        "clientes",
        "credenciais",
        "ginasios",
        "membros_equipa",
        "planos",
        "presencas",
        "versao_esquema",
    }
    assert "empresas" not in tabelas_empresa
    assert "utilizadores" not in tabelas_empresa
    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.connect() as connection:
            proprietario = connection.execute(
                text("SELECT utilizador_id, papel, ativo FROM membros_equipa")
            ).one()
    assert proprietario == ("adm-emp-a1", "proprietario", 1)


def test_provisionamento_e_repetivel_sem_duplicar_empresa_ou_ginasio(infraestrutura):
    controlo, gestor, _ = infraestrutura

    primeiro = provisionar(controlo, gestor, "emp-b2")
    segundo = provisionar(controlo, gestor, "emp-b2")

    assert segundo.estado == EstadoProvisionamento.ATIVO
    assert primeiro.caminho_base_dados == segundo.caminho_base_dados
    assert controlo.contar_empresas() == 1
    assert controlo.contar_administradores() == 1
    with ligar_base(segundo.caminho_base_dados) as engine:
        with engine.connect() as connection:
            assert connection.scalar(select(GinasioEmpresaRecord.id)) == "gym-emp-b2"


def test_provisionamento_isola_dados_em_arquivos_de_empresas_distintas(infraestrutura):
    controlo, gestor, _ = infraestrutura

    a = provisionar(controlo, gestor, "emp-c3")
    b = provisionar(controlo, gestor, "emp-d4")

    assert a.caminho_base_dados != b.caminho_base_dados
    assert a.caminho_base_dados.parent == b.caminho_base_dados.parent
    assert controlo.contar_empresas() == 2
    with ligar_base(a.caminho_base_dados) as engine_a:
        with engine_a.connect() as connection:
            assert connection.exec_driver_sql("SELECT id FROM ginasios").scalar_one() == "gym-emp-c3"
    with ligar_base(b.caminho_base_dados) as engine_b:
        with engine_b.connect() as connection:
            assert connection.exec_driver_sql("SELECT id FROM ginasios").scalar_one() == "gym-emp-d4"


def test_email_de_administrador_e_unico_globalmente(infraestrutura):
    controlo, gestor, _ = infraestrutura
    provisionar(controlo, gestor, "emp-e5", "global@example.test")

    with pytest.raises(ErroProvisionamento):
        provisionar(controlo, gestor, "emp-f6", "global@example.test")

    assert controlo.contar_empresas() == 1
    assert controlo.obter_empresa("emp-f6") is None


def test_falha_fica_visivel_e_repeticao_recupera_provisionamento(infraestrutura, monkeypatch):
    controlo, gestor, _ = infraestrutura
    provisionar_original = gestor.provisionar

    def falhar(*args, **kwargs):
        raise OSError("falha simulada de armazenamento")

    monkeypatch.setattr(gestor, "provisionar", falhar)
    with pytest.raises(OSError, match="falha simulada"):
        provisionar(controlo, gestor, "emp-g7")

    empresa_falhada = controlo.obter_empresa("emp-g7")
    assert empresa_falhada is not None
    assert empresa_falhada.estado == EstadoProvisionamento.FALHOU
    assert empresa_falhada.erro_provisionamento == "tenant_provisioning_failed"

    monkeypatch.setattr(gestor, "provisionar", provisionar_original)
    resultado = provisionar(controlo, gestor, "emp-g7")

    assert resultado.estado == EstadoProvisionamento.ATIVO
    assert controlo.contar_empresas() == 1


def test_base_de_empresa_rejeita_chave_de_caminho_e_segundo_ginasio(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-h8")

    with pytest.raises(ValueError, match="Chave de base de dados inválida"):
        gestor.provisionar(
            "../../gym_presence",
            "gym-externo",
            "Outro ginásio",
            "",
            "adm-emp-h8",
        )

    with ligar_base(resultado.caminho_base_dados) as engine:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    GinasioEmpresaRecord.__table__.insert().values(
                        singleton_id=2,
                        id="gym-2",
                        nome="Segundo ginásio",
                        endereco="",
                    )
                )


def test_repeticao_nao_altera_ginasio_ja_provisionado(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-i9")

    with pytest.raises(ConflitoBaseEmpresa):
        gestor.provisionar(
            "emp-i9",
            "gym-diferente",
            "Outro ginásio",
            "",
            "adm-emp-i9",
        )

    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT id FROM ginasios").scalar_one() == "gym-emp-i9"


def test_cliente_exige_assinatura_valida_na_mesma_base(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-k1")
    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO planos "
                    "(id, nome, descricao, dias_semana, duracao_maxima_minutos, ginasio_id, ativo) "
                    "VALUES ('plano-k1', 'Mensal', '', '[]', NULL, 'gym-emp-k1', 1)"
                )
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO clientes "
                        "(id, nome, email, telefone, ativo, assinatura_id) "
                        "VALUES ('cli-sem-sub', 'Sem assinatura', 'sem@example.test', '', 1, 'sub-ausente')"
                    )
                )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO clientes "
                    "(id, nome, email, telefone, ativo, assinatura_id) "
                    "VALUES ('cli-k1', 'Cliente', 'cliente@example.test', '', 1, 'sub-k1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO assinaturas "
                    "(id, cliente_id, plano_id, inicio, fim, estado) "
                    "VALUES ('sub-k1', 'cli-k1', 'plano-k1', "
                    "'2026-10-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', 'ativa')"
                )
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO clientes "
                        "(id, nome, email, telefone, ativo, assinatura_id) "
                        "VALUES ('cli-duplicado', 'Duplicado', 'CLIENTE@example.test', '', 1, 'sub-k1')"
                    )
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO clientes "
                        "(id, nome, email, telefone, ativo, assinatura_id) "
                        "VALUES ('cli-outro', 'Outro', 'outro@example.test', '', 1, 'sub-k2')"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO assinaturas "
                        "(id, cliente_id, plano_id, inicio, fim, estado) "
                        "VALUES ('sub-k2', 'cli-k1', 'plano-k1', "
                        "'2026-10-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', 'ativa')"
                    )
                )


def test_base_protege_administrador_ativo_minimo_e_ginasio_unico(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-l2")
    with ligar_base(resultado.caminho_base_dados) as engine:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO ginasios (singleton_id, id, nome, endereco) "
                        "VALUES (2, 'gym-extra', 'Outro', '')"
                    )
                )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE membros_equipa SET ativo = 0 WHERE utilizador_id = 'adm-emp-l2'")
                )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO membros_equipa "
                    "(utilizador_id, papel, ativo, criado_em) "
                    "VALUES ('adm-secundario', 'administrador', 1, "
                    "'2026-10-16T00:00:00+00:00')"
                )
            )
            connection.execute(
                text("UPDATE membros_equipa SET ativo = 0 WHERE utilizador_id = 'adm-secundario'")
            )


def test_presencas_sao_append_only_e_anulacao_exige_justificacao(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-m3")
    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO planos "
                    "(id, nome, descricao, dias_semana, ginasio_id, ativo) "
                    "VALUES ('plano-m3', 'Mensal', '', '[]', 'gym-emp-m3', 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO clientes "
                    "(id, nome, email, telefone, ativo, assinatura_id) "
                    "VALUES ('cli-m3', 'Cliente', 'm3@example.test', '', 1, 'sub-m3')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO assinaturas "
                    "(id, cliente_id, plano_id, inicio, fim, estado) "
                    "VALUES ('sub-m3', 'cli-m3', 'plano-m3', "
                    "'2026-10-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00', 'ativa')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO presencas "
                    "(id, cliente_id, ginasio_id, origem, autor_tipo, autor_id, entrada_em) "
                    "VALUES ('pres-m3', 'cli-m3', 'gym-emp-m3', "
                    "'manual', 'utilizador', 'adm-emp-m3', '2026-10-16T00:00:00+00:00')"
                )
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM presencas WHERE id = 'pres-m3'"))
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE presencas SET cliente_id = 'outro' WHERE id = 'pres-m3'")
                )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE presencas SET anulada_em = "
                        "'2026-10-16T01:00:00+00:00', anulada_por = 'adm-emp-m3' "
                        "WHERE id = 'pres-m3'"
                    )
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE presencas SET anulada_em = "
                    "'2026-10-16T01:00:00+00:00', anulada_por = 'adm-emp-m3', "
                    "motivo_anulacao = 'Correção autorizada' WHERE id = 'pres-m3'"
                )
            )


def test_auditoria_e_append_only(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-n4")
    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO auditoria "
                    "(id, ator_tipo, ator_id, acao, entidade_tipo, entidade_id, ocorrido_em) "
                    "VALUES ('audit-n4', 'utilizador', 'adm-emp-n4', "
                    "'empresa.criada', 'empresa', 'emp-n4', "
                    "'2026-10-16T00:00:00+00:00')"
                )
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE auditoria SET acao = 'alterada' WHERE id = 'audit-n4'")
                )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM auditoria WHERE id = 'audit-n4'"))


def test_repeticao_invalida_nao_marca_empresa_ativa_como_falhada(infraestrutura):
    controlo, gestor, _ = infraestrutura
    provisionar(controlo, gestor, "emp-j0")

    with pytest.raises(ConflitoBaseEmpresa):
        provisionar_empresa(
            controlo=controlo,
            bases_empresa=gestor,
            empresa=empresa("emp-j0"),
            administrador_id="adm-emp-j0",
            administrador_email="emp-j0@example.test",
            password_hash="hash-de-teste",
            ginasio=Ginasio(id="gym-emp-j0", nome="Nome divergente"),
        )

    registo = controlo.obter_empresa("emp-j0")
    assert registo is not None
    assert registo.estado == EstadoProvisionamento.ATIVO


def test_schema_antigo_nao_e_alterado_implicitamente(infraestrutura):
    controlo, gestor, _ = infraestrutura
    resultado = provisionar(controlo, gestor, "emp-o5")

    with ligar_base(resultado.caminho_base_dados) as engine:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE versao_esquema SET versao = 1 WHERE singleton_id = 1")
            )
        tabelas_antes = set(inspect(engine).get_table_names())

    with pytest.raises(ConflitoBaseEmpresa, match="migração de schema"):
        gestor.provisionar(
            "emp-o5",
            "gym-emp-o5",
            "Ginásio emp-o5",
            "",
            "adm-emp-o5",
        )

    with ligar_base(resultado.caminho_base_dados) as engine:
        assert set(inspect(engine).get_table_names()) == tabelas_antes
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT versao FROM versao_esquema WHERE singleton_id = 1")
            ) == 1
