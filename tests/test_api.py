"""Testes de autenticação, cadastro, assinaturas e presença pela API HTTP."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.data import store
from app.data.database import Base, engine
from app.main import app
from app.services.administracao import gerar_hash_senha

EMAIL_ADMIN = "admin@example.test"
SENHA_ADMIN = "SenhaDeTeste-Segura-2026"


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def autenticar_admin(client: TestClient) -> dict[str, str]:
    store.criar_primeiro_admin(EMAIL_ADMIN, gerar_hash_senha(SENHA_ADMIN))
    resposta = client.post(
        "/admin/login",
        json={"email": EMAIL_ADMIN, "password": SENHA_ADMIN},
    )
    assert resposta.status_code == 200
    return {"X-Admin-Token": resposta.json()["access_token"]}


def criar_ginasio_e_plano(client: TestClient, headers: dict[str, str]):
    resposta_ginasio = client.post(
        "/ginasios",
        json={"nome": "Unidade Teste", "endereco": "Rua de Teste"},
        headers=headers,
    )
    assert resposta_ginasio.status_code == 201
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
    assert resposta_plano.status_code == 201
    return ginasio_id, resposta_plano.json()


def criar_cliente(client: TestClient, headers: dict[str, str], plano_id: str):
    agora = datetime.now(timezone.utc)
    return client.post(
        "/clientes",
        json={
            "nome": "Cliente Teste",
            "email": "cliente@example.test",
            "telefone": "910000000",
            "plano_id": plano_id,
            "assinatura_inicio": (agora - timedelta(days=1)).isoformat(),
            "assinatura_fim": (agora + timedelta(days=30)).isoformat(),
            "credenciais": [{"metodo": "qr", "codigo": "QR-CLIENTE-001"}],
        },
        headers=headers,
    )


def test_health_e_rotas_publicas(client: TestClient):
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}
    assert client.get("/ginasios").json() == []
    assert client.get("/planos").json() == []


def test_login_e_protecao_admin(client: TestClient):
    assert client.get("/clientes").status_code == 401
    store.criar_primeiro_admin(EMAIL_ADMIN, gerar_hash_senha(SENHA_ADMIN))

    errado = client.post(
        "/admin/login",
        json={"email": EMAIL_ADMIN, "password": "senha-incorreta-123"},
    )
    assert errado.status_code == 401

    login = client.post(
        "/admin/login",
        json={"email": EMAIL_ADMIN.upper(), "password": SENHA_ADMIN},
    )
    assert login.status_code == 200
    assert login.json()["expires_in"] == 3600
    headers = {"X-Admin-Token": login.json()["access_token"]}
    assert client.get("/clientes", headers=headers).status_code == 200
    assert client.get("/clientes", headers={"X-Admin-Token": "invalido"}).status_code == 401


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

    entrada = client.post("/presencas/marcar", json={**marcacao, "tipo": "entrada"})
    assert entrada.status_code == 200
    entrada_duplicada = client.post(
        "/presencas/marcar", json={**marcacao, "tipo": "entrada"}
    )
    assert entrada_duplicada.status_code == 403
    saida = client.post("/presencas/marcar", json={**marcacao, "tipo": "saida"})
    assert saida.status_code == 200
    assert len(client.get("/presencas", headers=headers).json()) == 1