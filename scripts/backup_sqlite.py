"""Cria uma cópia consistente do banco SQLite em uso."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.data.database import engine
from app.data.paths import pasta_dados


def main() -> None:
    """Usa a API de backup do SQLite para copiar inclusive bancos em WAL."""
    origem = Path(engine.url.database or "")
    if not origem.is_file():
        raise SystemExit(f"Banco SQLite não encontrado: {origem}")

    pasta_backups = pasta_dados() / "backups"
    pasta_backups.mkdir(parents=True, exist_ok=True)
    momento = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = pasta_backups / f"gym_presence-{momento}.db"

    with sqlite3.connect(origem) as banco_origem:
        with sqlite3.connect(destino) as banco_copia:
            banco_origem.backup(banco_copia)
            resultado = banco_copia.execute("PRAGMA integrity_check").fetchone()[0]
    if resultado != "ok":
        destino.unlink(missing_ok=True)
        raise SystemExit("O backup não passou na verificação de integridade.")
    print(f"Backup verificado: {destino}")


if __name__ == "__main__":
    main()