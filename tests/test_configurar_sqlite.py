"""Testes da configuração inicial local do SQLite e do segredo administrativo."""

from scripts import configurar_sqlite


def test_configuracao_substitui_segredo_admin_vazio(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=production\nADMIN_TOKEN_SECRET=\nDATABASE_URL=sqlite:///old.db\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(configurar_sqlite, "ROOT", tmp_path)
    monkeypatch.setattr(configurar_sqlite, "ENV_FILE", env_file)
    monkeypatch.setattr(
        configurar_sqlite,
        "caminho_banco_padrao",
        lambda: tmp_path / "dados" / "gym_presence.db",
    )

    configurar_sqlite.main()

    linhas = env_file.read_text(encoding="utf-8").splitlines()
    segredo = next(
        linha.partition("=")[2]
        for linha in linhas
        if linha.startswith("ADMIN_TOKEN_SECRET=")
    )
    assert len(segredo) >= 32
    assert "APP_ENV=development" in linhas
    assert not any(linha.startswith("DATABASE_URL=") for linha in linhas)
