"""Schemas de entrada e saída e validação dos dados da aplicação."""

from datetime import datetime, time
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MetodoAcesso = Literal["biometria", "face", "cartao", "pin", "qr"]
TipoMarcacao = Literal["entrada", "saida"]


class Requisicao(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Plano(BaseModel):
    id: str
    nome: str
    descricao: str = ""
    max_visitas_semana: Optional[int] = None
    max_visitas_mes: Optional[int] = None
    hora_inicio: Optional[time] = None
    hora_fim: Optional[time] = None
    dias_semana: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    duracao_maxima_minutos: Optional[int] = None
    ginasios_permitidos: list[str] = Field(default_factory=list)
    ativo: bool = True


class Empresa(BaseModel):
    id: str
    nome: str
    email: str
    telefone: str = ""
    endereco: str = ""


class EmpresaDados(Requisicao):
    nome: str = Field(min_length=1, max_length=160)
    email: str
    telefone: str = Field(default="", max_length=80)
    endereco: str = Field(default="", max_length=300)

    @field_validator("nome")
    @classmethod
    def normalizar_nome_empresa(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome da empresa não pode estar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email_empresa(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor) is None:
            raise ValueError("Endereço de email da empresa inválido.")
        return valor


class EmpresaAtualizacao(Requisicao):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=160)
    email: Optional[str] = None
    telefone: Optional[str] = Field(default=None, max_length=80)
    endereco: Optional[str] = Field(default=None, max_length=300)

    @field_validator("nome")
    @classmethod
    def normalizar_nome_empresa(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome da empresa não pode estar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email_empresa(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor) is None:
            raise ValueError("Endereço de email da empresa inválido.")
        return valor

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Indique pelo menos um campo da empresa.")
        return self


class Credencial(BaseModel):
    metodo: MetodoAcesso
    codigo: str = Field(min_length=1, max_length=250)

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O código da credencial não pode estar vazio.")
        return valor


class Cliente(BaseModel):
    id: str
    nome: str
    email: str
    telefone: str = ""
    plano_id: str
    assinatura_inicio: datetime
    assinatura_fim: datetime
    credenciais: list[Credencial] = Field(default_factory=list)
    ativo: bool = True


class Ginasio(BaseModel):
    id: str
    nome: str
    endereco: str = ""


class GinasioCreate(Requisicao):
    nome: str = Field(min_length=1, max_length=160)
    endereco: str = Field(default="", max_length=300)

    @field_validator("nome")
    @classmethod
    def normalizar_nome_ginasio(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome do ginásio não pode estar vazio.")
        return valor


class AdminRegistro(Requisicao):
    email: str
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalizar_email_admin(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor) is None:
            raise ValueError("Endereço de email inválido.")
        return valor


class CadastroEmpresa(Requisicao):
    empresa: EmpresaDados
    administrador: AdminRegistro
    ginasio: GinasioCreate


class Presenca(BaseModel):
    id: str
    cliente_id: str
    ginasio_id: str
    metodo: MetodoAcesso
    entrada_em: datetime
    saida_em: Optional[datetime] = None


class MarcacaoRequest(Requisicao):
    ginasio_id: str
    metodo: MetodoAcesso
    credencial: str
    tipo: Optional[TipoMarcacao] = None


class AdminLogin(Requisicao):
    email: str
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalizar_email_admin(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor) is None:
            raise ValueError("Endereço de email inválido.")
        return valor


class PlanoCreate(Requisicao):
    nome: str = Field(min_length=1, max_length=100)
    descricao: str = ""
    max_visitas_semana: Optional[int] = Field(default=None, ge=0)
    max_visitas_mes: Optional[int] = Field(default=None, ge=0)
    hora_inicio: Optional[time] = None
    hora_fim: Optional[time] = None
    dias_semana: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    duracao_maxima_minutos: Optional[int] = Field(default=None, gt=0)
    ginasios_permitidos: list[str] = Field(default_factory=list)
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome do plano não pode estar vazio.")
        return valor

    @field_validator("dias_semana")
    @classmethod
    def validar_dias_semana(cls, dias: list[int]) -> list[int]:
        if len(set(dias)) != len(dias) or any(dia not in range(7) for dia in dias):
            raise ValueError("Os dias da semana devem ser únicos e estar entre 0 e 6.")
        return dias

    @field_validator("ginasios_permitidos")
    @classmethod
    def validar_ginasios_unicos(cls, ginasios: list[str]) -> list[str]:
        if len(set(ginasios)) != len(ginasios):
            raise ValueError("Os ginásios permitidos devem ser únicos.")
        return ginasios

    @model_validator(mode="after")
    def validar_horario(self):
        if self.hora_inicio and self.hora_fim and self.hora_inicio >= self.hora_fim:
            raise ValueError("A hora de início deve ser anterior à hora de fim.")
        return self


class ClienteCreate(Requisicao):
    nome: str = Field(min_length=1, max_length=120)
    email: str
    telefone: str = ""
    plano_id: str
    assinatura_inicio: datetime
    assinatura_fim: datetime
    credenciais: list[Credencial] = Field(default_factory=list)

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome do cliente não pode estar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor) is None:
            raise ValueError("Endereço de email inválido.")
        return valor

    @model_validator(mode="after")
    def validar_assinatura(self):
        if (self.assinatura_inicio.utcoffset() is None) != (
            self.assinatura_fim.utcoffset() is None
        ):
            raise ValueError("As datas da assinatura devem usar o mesmo fuso horário.")
        if self.assinatura_inicio >= self.assinatura_fim:
            raise ValueError("O início da assinatura deve ser anterior ao fim.")
        return self


class AssinaturaUpdate(Requisicao):
    plano_id: Optional[str] = None
    assinatura_inicio: Optional[datetime] = None
    assinatura_fim: Optional[datetime] = None

    @model_validator(mode="after")
    def validar_campos(self):
        if not self.model_fields_set:
            raise ValueError("Indique pelo menos um campo da assinatura.")
        if self.assinatura_inicio is not None and self.assinatura_fim is not None:
            if (self.assinatura_inicio.utcoffset() is None) != (
                self.assinatura_fim.utcoffset() is None
            ):
                raise ValueError("As datas da assinatura devem usar o mesmo fuso horário.")
            if self.assinatura_inicio >= self.assinatura_fim:
                raise ValueError("O início da assinatura deve ser anterior ao fim.")
        return self
