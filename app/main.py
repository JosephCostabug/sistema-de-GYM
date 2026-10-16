import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data import store
from app.routes.administracao import router as administracao_router
from app.routes.clientes import router as clientes_router
from app.routes.empresas import router as empresas_router
from app.routes.ginasios import router as ginasios_router
from app.routes.planos import router as planos_router
from app.routes.presencas import router as presencas_router
from app.routes.saude import router as saude_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Cria as tabelas e os dados de exemplo antes de aceitar pedidos."""
    store.inicializar()
    yield


app = FastAPI(
    title="Gym Presence",
    description="Marcação de presença em ginásio por biometria, face, cartão e outros métodos, limitada pelo plano do cliente.",
    lifespan=lifespan,
)

# Origens locais padrão de desenvolvimento
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5500",
    "http://localhost:8800",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# CORREÇÃO AQUI: Lendo a variável correta estipulada no contrato (FRONTEND_ORIGINS)
frontend_origins_env = os.getenv("FRONTEND_ORIGINS")
if frontend_origins_env:
    adicionais = [origem.strip() for origem in frontend_origins_env.split(",")]
    origins.extend(adicionais)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)

@app.get("/")
async def read_root():
    return {"message": "Bem-vindo ao Gym Presence!"}

app.include_router(ginasios_router)
app.include_router(empresas_router)
app.include_router(administracao_router)
app.include_router(planos_router)
app.include_router(clientes_router)
app.include_router(presencas_router)
app.include_router(saude_router)
