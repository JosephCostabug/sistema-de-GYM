"""Caminhos locais persistentes, fora da pasta sincronizada do workspace."""

import os
from pathlib import Path


def pasta_dados() -> Path:
    """Retorna a pasta de dados por usuário apropriada ao sistema operacional."""
    raiz = os.getenv("LOCALAPPDATA") or os.getenv("XDG_DATA_HOME")
    if raiz:
        caminho = Path(raiz) / "GymPresence"
    else:
        caminho = Path.home() / ".local" / "share" / "gym-presence"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def caminho_banco_padrao() -> Path:
    """Aponta para o arquivo principal SQLite persistente."""
    return pasta_dados() / "gym_presence.db"