"""Configuração isolada dos testes HTTP com SQLite em memória."""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///"
os.environ["ADMIN_TOKEN_SECRET"] = "test-only-secret-key-not-for-use-outside-tests"