"""Autenticação administrativa, armazenamento de senha e tokens de acesso."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Header, HTTPException, status

from app.data import store

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_TOKEN_TTL_SECONDS = 60 * 60


def gerar_hash_senha(senha: str) -> str:
    """Gera hash resistente a tentativas de adivinhação; a senha não é persistida."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        senha.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=64,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verificar_senha(senha: str, password_hash: str) -> bool:
    """Compara senha e hash em tempo constante, rejeitando formatos desconhecidos."""
    try:
        algoritmo, n, r, p, salt_hex, digest_hex = password_hash.split("$")
        if (
            algoritmo != "scrypt"
            or int(n) != _SCRYPT_N
            or int(r) != _SCRYPT_R
            or int(p) != _SCRYPT_P
            or len(bytes.fromhex(salt_hex)) != 16
            or len(bytes.fromhex(digest_hex)) != 64
        ):
            return False
        digest = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=64,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def criar_token(admin_id: str) -> tuple[str, int]:
    """Assina um token de sessão com validade curta usando segredo externo."""
    segredo = os.getenv("ADMIN_TOKEN_SECRET")
    if not segredo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure ADMIN_TOKEN_SECRET para habilitar o login admin.",
        )

    expiracao = int(time.time()) + _TOKEN_TTL_SECONDS
    conteudo = _base64url(
        json.dumps({"sub": admin_id, "exp": expiracao}, separators=(",", ":")).encode()
    )
    assinatura = _assinar(conteudo, segredo)
    return f"{conteudo}.{assinatura}", _TOKEN_TTL_SECONDS


def validar_token(token: str | None) -> str:
    """Valida assinatura e expiração e devolve o identificador do admin."""
    segredo = os.getenv("ADMIN_TOKEN_SECRET")
    if not segredo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure ADMIN_TOKEN_SECRET para habilitar o login admin.",
        )
    if not token:
        raise _token_invalido()

    try:
        conteudo, assinatura = token.split(".", maxsplit=1)
        if not hmac.compare_digest(assinatura, _assinar(conteudo, segredo)):
            raise _token_invalido()
        dados = json.loads(_decode_base64url(conteudo))
        admin_id = dados["sub"]
        expiracao = int(dados["exp"])
        if not isinstance(admin_id, str) or expiracao <= int(time.time()):
            raise _token_invalido()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise _token_invalido() from None
    return admin_id


def exigir_administrador(
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Protege rotas administrativas com token de uma conta ativa."""
    admin_id = validar_token(x_admin_token)
    if not store.admin_ativo(admin_id):
        raise _token_invalido()


def _assinar(conteudo: str, segredo: str) -> str:
    digest = hmac.new(segredo.encode("utf-8"), conteudo.encode("ascii"), hashlib.sha256)
    return _base64url(digest.digest())


def _base64url(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).rstrip(b"=").decode("ascii")


def _decode_base64url(valor: str) -> bytes:
    return base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))


def _token_invalido() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token administrativo inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )