"""Testes HTTP de cadastro, isolamento por empresa e presença."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.data.database import Base, engine
from app.main import app

SENHA_ADMIN = "SenhaDeTeste-Segura-2026"


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def registrar_empresa(
    client: TestClient,
    email_admin: str = "admin@example.test",
    nome_empresa: str = "Empresa Teste",
    nome_ginasio: str = "Ginasio Inicial",
):
    resposta = client.post(
        "/admin/register",
        json={
            "empresa": {
                "nome": nome_empresa,
                "email": f"contacto+{email_admin}",
                "telefone": "210000000",
                "endereco": "Rua da Empresa",
            },
            "administrador": {
                "email": email_admin,
                "password": SENHA_ADMIN,
            },
            "ginasio": {
                "nome": nome_ginasio,
                "endereco": "Rua do Ginasio",
            },
        },
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def autenticar_admin(
    client: TestClient,
    email_admin: str = "admin@example.test",
    nome_empresa: str = "Empresa Teste",
) -> dict[str, str]:
    registrar_empresa(client, email_admin, nome_empresa)
    resposta = client.post(
        "/admin/login",
        json={"email": email_admin, "password": SENHA_ADMIN},
    )
    assert resposta.status_code == 200, resposta.text
    return {"X-Admin-Token": resposta.json()["access_token"]}


def criar_ginasio_e_plano(client: TestClient, headers: dict[str, str]):
    resposta_ginasio = client.post(
        "/ginasios",
        json={"nome": "Unidade Adicional", "endereco": "Rua de Teste"},
        headers=headers,
    )
    assert resposta_ginasio.status_code == 201, resposta_ginasio.text
    ginasio_id = resposta_ginasio.json()["id"]

    resposta_plano = client.post(
        "/planos",
        json={
            "nome": "Plano Teste",
            "max_visitas_semana": 2,
            "max_visitas_mes": 8,
            "dias_semana": list(range(7)),
            "ginasios_permitidos": [ginasio_id],
        },
        headers=headers,
    )
    assert resposta_plano.status_code == 201, resposta_plano.text
    return ginasio_id, resposta_plano.json()


def criar_cliente(
    client: TestClient,
    headers: dict[str, str],
    plano_id: str,
    email: str = "cliente@example.test",
    codigo: str = "QR-CLIENTE-001",
    nome: str = "Cliente Teste",
):
    agora = datetime.now(timezone.utc)
    return client.post(
        "/clientes",
        json={
            "nome": nome,
            "email": email,
            "telefone": "910000000",
            "plano_id": plano_id,
            "assinatura_inicio": (agora - timedelta(days=1)).isoformat(),
            "assinatura_fim": (agora + timedelta(days=30)).isoformat(),
            "credenciais": [{"metodo": "qr", "codigo": codigo}],
        },
        headers=headers,
    )


def test_health_e_endpoints_privados(client: TestClient):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    for caminho in ("/empresa", "/ginasios", "/planos", "/clientes", "/presencas"):
        assert client.get(caminho).status_code == 401


def test_cors_permite_frontend_local_e_bloqueia_origem_externa(client: TestClient):
    permitido = client.options(
        "/clientes",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-admin-token",
        },
    )
    assert permitido.status_code == 200
    assert permitido.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-admin-token" in permitido.headers["access-control-allow-headers"].lower()

    bloqueado = client.options(
        "/clientes",
        headers={
            "Origin": "https://origem-nao-autorizada.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in bloqueado.headers


def test_cadastro_empresa_e_login_admin(client: TestClient):
    cadastro = registrar_empresa(client)
    assert cadastro["empresa"]["nome"] == "Empresa Teste"
    assert cadastro["ginasio"]["nome"] == "Ginasio Inicial"
    assert cadastro["expires_in"] == 3600

    errado = client.post(
        "/admin/login",
        json={"email": "admin@example.test", "password": "senha-incorreta-123"},
    )
    assert errado.status_code == 401

    login = client.post(
        "/admin/login",
        json={"email": "ADMIN@EXAMPLE.TEST", "password": SENHA_ADMIN},
    )
    assert login.status_code == 200
    headers = {"X-Admin-Token": login.json()["access_token"]}
    assert client.get("/empresa", headers=headers).json()["nome"] == "Empresa Teste"
    assert client.get("/ginasios", headers=headers).json()[0]["nome"] == "Ginasio Inicial"
    assert client.get("/clientes", headers=headers).status_code == 200
    assert client.get("/clientes", headers={"X-Admin-Token": "invalido"}).status_code == 401


def test_cadastro_empresa_e_atomico_e_email_admin_unico(client: TestClient):
    registrar_empresa(client)
    duplicado = client.post(
        "/admin/register",
        json={
            "empresa": {"nome": "Outra", "email": "outra@example.test"},
            "administrador": {
                "email": "ADMIN@example.test",
                "password": SENHA_ADMIN,
            },
            "ginasio": {"nome": "Unidade"},
        },
    )
    assert duplicado.status_code == 409

    headers = {
        "X-Admin-Token": client.post(
            "/admin/login",
            json={"email": "admin@example.test", "password": SENHA_ADMIN},
        ).json()["access_token"]
    }
    assert len(client.get("/ginasios", headers=headers).json()) == 1


def test_perfil_ginasios_planos_e_clientes_isolados_por_empresa(client: TestClient):
    headers_a = autenticar_admin(client, "admin-a@example.test", "Empresa A")
    headers_b = autenticar_admin(client, "admin-b@example.test", "Empresa B")

    perfil = client.get("/empresa", headers=headers_a)
    assert perfil.status_code == 200
    atualizado = client.patch(
        "/empresa",
        json={"telefone": "220000000"},
        headers=headers_a,
    )
    assert atualizado.status_code == 200
    assert atualizado.json()["telefone"] == "220000000"
    assert client.get("/empresa", headers=headers_b).json()["telefone"] == "210000000"

    ginasio_a = client.get("/ginasios", headers=headers_a).json()[0]
    ginasio_b = client.get("/ginasios", headers=headers_b).json()[0]
    assert ginasio_a["id"] != ginasio_b["id"]

    plano_a = client.post(
        "/planos",
        json={
            "nome": "Plano A",
            "ginasios_permitidos": [ginasio_a["id"]],
        },
        headers=headers_a,
    )
    assert plano_a.status_code == 201
    assert client.get(
        f"/planos/{plano_a.json()['id']}",
        headers=headers_b,
    ).status_code == 404
    assert client.put(
        f"/planos/{plano_a.json()['id']}",
        json={
            "nome": "Plano alterado",
            "ginasios_permitidos": [ginasio_b["id"]],
        },
        headers=headers_b,
    ).status_code == 404

    plano_b = client.post(
        "/planos",
        json={
            "nome": "Plano B",
            "ginasios_permitidos": [ginasio_b["id"]],
        },
        headers=headers_b,
    )
    assert plano_b.status_code == 201

    cliente_a = criar_cliente(
        client,
        headers_a,
        plano_a.json()["id"],
        email="cliente@exemplo.test",
        codigo="QR-EMPRESA",
        nome="Cliente A",
    )
    cliente_b = criar_cliente(
        client,
        headers_b,
        plano_b.json()["id"],
        email="cliente@exemplo.test",
        codigo="QR-EMPRESA",
        nome="Cliente B",
    )
    assert cliente_a.status_code == 201, cliente_a.text
    assert cliente_b.status_code == 201, cliente_b.text
    assert [item["nome"] for item in client.get("/clientes", headers=headers_a).json()] == [
        "Cliente A"
    ]
    assert [item["nome"] for item in client.get("/clientes", headers=headers_b).json()] == [
        "Cliente B"
    ]
    assert client.get(
        f"/clientes/{cliente_a.json()['id']}",
        headers=headers_b,
    ).status_code == 404
    assert client.patch(
        f"/clientes/{cliente_a.json()['id']}/assinatura",
        json={"plano_id": plano_b.json()["id"]},
        headers=headers_b,
    ).status_code == 404
    assert criar_cliente(
        client,
        headers_b,
        plano_a.json()["id"],
        email="cliente-plano-externo@exemplo.test",
        codigo="QR-EXTERNO",
    ).status_code == 404

    marcacao = {
        "metodo": "qr",
        "credencial": "QR-EMPRESA",
        "tipo": "entrada",
    }
    entrada_a = client.post(
        "/presencas/marcar",
        json={**marcacao, "ginasio_id": ginasio_a["id"]},
        headers=headers_a,
    )
    entrada_b = client.post(
        "/presencas/marcar",
        json={**marcacao, "ginasio_id": ginasio_b["id"]},
        headers=headers_b,
    )
    assert entrada_a.status_code == entrada_b.status_code == 200
    assert entrada_a.json()["cliente"] == "Cliente A"
    assert entrada_b.json()["cliente"] == "Cliente B"
    assert len(client.get("/presencas", headers=headers_a).json()) == 1
    assert len(client.get("/presencas", headers=headers_b).json()) == 1


def test_plano_nao_pode_referenciar_ginasio_de_outra_empresa(client: TestClient):
    headers_a = autenticar_admin(client, "admin-a@example.test", "Empresa A")
    headers_b = autenticar_admin(client, "admin-b@example.test", "Empresa B")
    ginasio_a = client.get("/ginasios", headers=headers_a).json()[0]

    resposta = client.post(
        "/planos",
        json={
            "nome": "Plano externo",
            "ginasios_permitidos": [ginasio_a["id"]],
        },
        headers=headers_b,
    )
    assert resposta.status_code == 404


def test_marcar_presenca_exige_sessao_e_tenant_da_sessao(client: TestClient):
    headers_a = autenticar_admin(client, "admin-a@example.test", "Empresa A")
    headers_b = autenticar_admin(client, "admin-b@example.test", "Empresa B")
    ginasio_a, plano_a = criar_ginasio_e_plano(client, headers_a)
    ginasio_b, plano_b = criar_ginasio_e_plano(client, headers_b)
    criar_cliente(
        client,
        headers_a,
        plano_a["id"],
        email="cliente-a@example.test",
        codigo="QR-A",
    )
    criar_cliente(
        client,
        headers_b,
        plano_b["id"],
        email="cliente-b@example.test",
        codigo="QR-B",
    )
    pedido = {"ginasio_id": ginasio_a, "metodo": "qr", "credencial": "QR-A"}

    assert client.post("/presencas/marcar", json=pedido).status_code == 401
    assert client.post(
        "/presencas/marcar",
        json={**pedido, "ginasio_id": ginasio_b},
        headers=headers_a,
    ).status_code == 404
    assert client.post(
        "/presencas/marcar",
        json={**pedido, "empresa_id": "empresa-b"},
        headers=headers_a,
    ).status_code == 422
    assert client.post(
        "/presencas/marcar",
        json=pedido,
        headers=headers_a,
    ).status_code == 200


def test_cadastro_cliente_e_duplicados(client: TestClient):
    headers = autenticar_admin(client)
    _, plano = criar_ginasio_e_plano(client, headers)
    resposta = criar_cliente(client, headers, plano["id"])

    assert resposta.status_code == 201
    assert resposta.json()["email"] == "cliente@example.test"
    duplicado_email = criar_cliente(client, headers, plano["id"])
    assert duplicado_email.status_code == 409

    duplicado_credencial = client.post(
        "/clientes",
        json={
            "nome": "Outra Pessoa",
            "email": "outra@example.test",
            "plano_id": plano["id"],
            "assinatura_inicio": "2026-10-10T00:00:00+00:00",
            "assinatura_fim": "2026-11-10T00:00:00+00:00",
            "credenciais": [{"metodo": "qr", "codigo": "QR-CLIENTE-001"}],
        },
        headers=headers,
    )
    assert duplicado_credencial.status_code == 409


def test_atualizar_assinatura_parcial(client: TestClient):
    headers = autenticar_admin(client)
    _, plano = criar_ginasio_e_plano(client, headers)
    cliente = criar_cliente(client, headers, plano["id"]).json()
    resposta = client.patch(
        f"/clientes/{cliente['id']}/assinatura",
        json={"assinatura_fim": "2027-01-01T00:00:00+00:00"},
        headers=headers,
    )
    assert resposta.status_code == 200
    assert resposta.json()["assinatura_fim"].startswith("2027-01-01")


def test_presenca_entrada_saida_e_limite(client: TestClient):
    headers = autenticar_admin(client)
    ginasio_id, plano = criar_ginasio_e_plano(client, headers)
    resposta_cliente = criar_cliente(client, headers, plano["id"])
    assert resposta_cliente.status_code == 201
    marcacao = {
        "ginasio_id": ginasio_id,
        "metodo": "qr",
        "credencial": "QR-CLIENTE-001",
    }

    entrada = client.post(
        "/presencas/marcar",
        json={**marcacao, "tipo": "entrada"},
        headers=headers,
    )
    assert entrada.status_code == 200
    entrada_duplicada = client.post(
        "/presencas/marcar",
        json={**marcacao, "tipo": "entrada"},
        headers=headers,
    )
    assert entrada_duplicada.status_code == 403
    saida = client.post(
        "/presencas/marcar",
        json={**marcacao, "tipo": "saida"},
        headers=headers,
    )
    assert saida.status_code == 200
    assert len(client.get("/presencas", headers=headers).json()) == 1
