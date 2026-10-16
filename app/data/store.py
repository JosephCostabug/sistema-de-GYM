"""Repositório transacional que traduz registros SQLAlchemy para schemas."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.data.database import (
    AdminAccountRecord,
    AttendanceRecord,
    Base,
    ClientRecord,
    CompanyRecord,
    CredentialRecord,
    GymRecord,
    PlanRecord,
    SessionLocal,
    engine,
)
from app.data.migrations import migrar_empresas
from app.models.schemas import Cliente, Credencial, Empresa, Ginasio, Plano, Presenca


class RegistroDuplicado(Exception):
    pass


class AdministradorJaExiste(Exception):
    pass


class EntradaJaAberta(Exception):
    pass


def novo_id() -> str:
    return uuid4().hex[:12]


def inicializar() -> None:
    """Cria o schema e migra registros existentes para uma empresa legada."""
    Base.metadata.create_all(bind=engine)
    migrar_empresas(engine)


def criar_empresa_com_administrador(
    empresa: Empresa,
    administrador_id: str,
    administrador_email: str,
    password_hash: str,
    ginasio: Ginasio,
) -> tuple[Empresa, Ginasio]:
    """Cria a empresa, seu primeiro administrador e ginásio numa transação."""
    try:
        with SessionLocal.begin() as session:
            session.add(CompanyRecord(**empresa.model_dump()))
            session.flush()
            session.add(
                AdminAccountRecord(
                    id=administrador_id,
                    empresa_id=empresa.id,
                    email=administrador_email,
                    password_hash=password_hash,
                    ativo=True,
                    criado_em=datetime.now(timezone.utc),
                )
            )
            session.add(
                GymRecord(
                    id=ginasio.id,
                    empresa_id=empresa.id,
                    nome=ginasio.nome,
                    endereco=ginasio.endereco,
                )
            )
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return empresa, ginasio


def obter_empresa(empresa_id: str) -> Empresa | None:
    with SessionLocal() as session:
        registro = session.get(CompanyRecord, empresa_id)
        return None if registro is None else _empresa(registro)


def atualizar_empresa(empresa_id: str, dados: dict) -> Empresa | None:
    with SessionLocal.begin() as session:
        registro = session.get(CompanyRecord, empresa_id)
        if registro is None:
            return None
        for campo, valor in dados.items():
            setattr(registro, campo, valor)
        resultado = _empresa(registro)
    return resultado


def listar_ginasios(empresa_id: str) -> list[Ginasio]:
    with SessionLocal() as session:
        registros = session.scalars(
            select(GymRecord)
            .where(GymRecord.empresa_id == empresa_id)
            .order_by(GymRecord.nome)
        ).all()
        return [_ginasio(registro) for registro in registros]


def obter_ginasio(ginasio_id: str, empresa_id: str) -> Ginasio | None:
    with SessionLocal() as session:
        registro = session.scalar(
            select(GymRecord).where(
                GymRecord.id == ginasio_id,
                GymRecord.empresa_id == empresa_id,
            )
        )
        return None if registro is None else _ginasio(registro)


def criar_ginasio(ginasio: Ginasio, empresa_id: str) -> Ginasio:
    try:
        with SessionLocal.begin() as session:
            session.add(
                GymRecord(
                    id=ginasio.id,
                    empresa_id=empresa_id,
                    nome=ginasio.nome,
                    endereco=ginasio.endereco,
                )
            )
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return ginasio


def listar_planos(empresa_id: str) -> list[Plano]:
    with SessionLocal() as session:
        registros = session.scalars(
            select(PlanRecord)
            .where(PlanRecord.empresa_id == empresa_id)
            .order_by(PlanRecord.nome)
        ).all()
        return [_plano(registro) for registro in registros]


def obter_plano(plano_id: str, empresa_id: str) -> Plano | None:
    with SessionLocal() as session:
        registro = session.scalar(
            select(PlanRecord).where(
                PlanRecord.id == plano_id,
                PlanRecord.empresa_id == empresa_id,
            )
        )
        return None if registro is None else _plano(registro)


def criar_plano(plano: Plano, empresa_id: str) -> Plano:
    try:
        with SessionLocal.begin() as session:
            session.add(PlanRecord(empresa_id=empresa_id, **plano.model_dump()))
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return plano


def atualizar_plano(plano_id: str, empresa_id: str, dados: dict) -> Plano | None:
    with SessionLocal.begin() as session:
        registro = session.scalar(
            select(PlanRecord).where(
                PlanRecord.id == plano_id,
                PlanRecord.empresa_id == empresa_id,
            )
        )
        if registro is None:
            return None
        for campo, valor in dados.items():
            setattr(registro, campo, valor)
        resultado = _plano(registro)
    return resultado


def listar_clientes(empresa_id: str) -> list[Cliente]:
    with SessionLocal() as session:
        registros = session.scalars(
            select(ClientRecord)
            .where(ClientRecord.empresa_id == empresa_id)
            .order_by(ClientRecord.nome)
        ).all()
        return [_cliente(registro) for registro in registros]


def obter_cliente(cliente_id: str, empresa_id: str) -> Cliente | None:
    with SessionLocal() as session:
        registro = session.scalar(
            select(ClientRecord).where(
                ClientRecord.id == cliente_id,
                ClientRecord.empresa_id == empresa_id,
            )
        )
        return None if registro is None else _cliente(registro)


def email_em_uso(email: str, empresa_id: str) -> bool:
    with SessionLocal() as session:
        return session.scalar(
            select(ClientRecord.id)
            .where(ClientRecord.email == email, ClientRecord.empresa_id == empresa_id)
            .limit(1)
        ) is not None


def credenciais_em_uso(empresa_id: str) -> set[tuple[str, str]]:
    with SessionLocal() as session:
        resultados = session.execute(
            select(CredentialRecord.metodo, CredentialRecord.codigo).where(
                CredentialRecord.empresa_id == empresa_id
            )
        ).all()
        return {(metodo, codigo) for metodo, codigo in resultados}


def obter_admin_por_email(email: str) -> dict | None:
    with SessionLocal() as session:
        registro = session.scalar(
            select(AdminAccountRecord).where(AdminAccountRecord.email == email)
        )
        return None if registro is None else _dados_admin(registro)


def obter_admin_por_id(admin_id: str) -> dict | None:
    with SessionLocal() as session:
        registro = session.get(AdminAccountRecord, admin_id)
        return None if registro is None else _dados_admin(registro)


def criar_administrador_empresa(
    empresa_id: str,
    administrador_id: str,
    email: str,
    password_hash: str,
) -> None:
    try:
        with SessionLocal.begin() as session:
            session.add(
                AdminAccountRecord(
                    id=administrador_id,
                    empresa_id=empresa_id,
                    email=email,
                    password_hash=password_hash,
                    ativo=True,
                    criado_em=datetime.now(timezone.utc),
                )
            )
    except IntegrityError as erro:
        raise RegistroDuplicado from erro


def _dados_admin(registro: AdminAccountRecord) -> dict:
    return {
        "id": registro.id,
        "empresa_id": registro.empresa_id,
        "email": registro.email,
        "password_hash": registro.password_hash,
        "ativo": registro.ativo,
    }


def atualizar_senha_admin(email: str, password_hash: str) -> bool:
    """Troca o hash de senha por procedimento operacional local."""
    with SessionLocal.begin() as session:
        registro = session.scalar(
            select(AdminAccountRecord).where(AdminAccountRecord.email == email)
        )
        if registro is None:
            return False
        registro.password_hash = password_hash
    return True


def criar_cliente(cliente: Cliente, empresa_id: str) -> Cliente:
    try:
        with SessionLocal.begin() as session:
            session.add(_registro_cliente(cliente, empresa_id))
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return cliente


def atualizar_assinatura(
    cliente_id: str,
    empresa_id: str,
    dados: dict,
) -> Cliente | None:
    with SessionLocal.begin() as session:
        registro = session.scalar(
            select(ClientRecord).where(
                ClientRecord.id == cliente_id,
                ClientRecord.empresa_id == empresa_id,
            )
        )
        if registro is None:
            return None
        for campo, valor in dados.items():
            if campo in {"assinatura_inicio", "assinatura_fim"}:
                valor = _para_utc(valor)
            setattr(registro, campo, valor)
        resultado = _cliente(registro)
    return resultado


def cliente_por_credencial(
    metodo: str,
    codigo: str,
    empresa_id: str,
) -> Cliente | None:
    with SessionLocal() as session:
        registro = session.scalars(
            select(ClientRecord)
            .join(CredentialRecord)
            .where(
                ClientRecord.empresa_id == empresa_id,
                CredentialRecord.empresa_id == empresa_id,
                CredentialRecord.metodo == metodo,
                CredentialRecord.codigo == codigo,
            )
        ).first()
        return None if registro is None else _cliente(registro)


def presenca_aberta(cliente_id: str, empresa_id: str) -> Presenca | None:
    with SessionLocal() as session:
        registro = session.scalars(
            select(AttendanceRecord)
            .where(
                AttendanceRecord.cliente_id == cliente_id,
                AttendanceRecord.empresa_id == empresa_id,
                AttendanceRecord.saida_em.is_(None),
            )
            .order_by(AttendanceRecord.entrada_em.desc())
            .limit(1)
        ).first()
        return None if registro is None else _presenca(registro)


def contar_visitas(cliente_id: str, empresa_id: str, desde: datetime) -> int:
    with SessionLocal() as session:
        return session.scalar(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.cliente_id == cliente_id,
                AttendanceRecord.empresa_id == empresa_id,
                AttendanceRecord.entrada_em >= _para_utc(desde),
            )
        ) or 0


def criar_presenca(presenca: Presenca, empresa_id: str) -> Presenca:
    try:
        with SessionLocal.begin() as session:
            session.add(
                AttendanceRecord(
                    id=presenca.id,
                    empresa_id=empresa_id,
                    cliente_id=presenca.cliente_id,
                    ginasio_id=presenca.ginasio_id,
                    metodo=presenca.metodo,
                    entrada_em=_para_utc(presenca.entrada_em),
                    saida_em=None,
                )
            )
    except IntegrityError as erro:
        raise EntradaJaAberta from erro
    return presenca


def fechar_presenca(
    presenca_id: str,
    empresa_id: str,
    saida_em: datetime,
) -> Presenca | None:
    with SessionLocal.begin() as session:
        resultado = session.execute(
            update(AttendanceRecord)
            .where(
                AttendanceRecord.id == presenca_id,
                AttendanceRecord.empresa_id == empresa_id,
                AttendanceRecord.saida_em.is_(None),
            )
            .values(saida_em=_para_utc(saida_em))
        )
        if resultado.rowcount == 0:
            return None
        registro = session.get(AttendanceRecord, presenca_id)
        resultado = _presenca(registro)
    return resultado


def listar_presencas(empresa_id: str) -> list[tuple[Presenca, str | None, str | None]]:
    with SessionLocal() as session:
        registros = session.execute(
            select(AttendanceRecord, ClientRecord.nome, GymRecord.nome)
            .outerjoin(ClientRecord, AttendanceRecord.cliente_id == ClientRecord.id)
            .outerjoin(GymRecord, AttendanceRecord.ginasio_id == GymRecord.id)
            .where(AttendanceRecord.empresa_id == empresa_id)
            .order_by(AttendanceRecord.entrada_em.desc())
        ).all()
        return [
            (_presenca(presenca), cliente, ginasio)
            for presenca, cliente, ginasio in registros
        ]


def _registro_cliente(cliente: Cliente, empresa_id: str) -> ClientRecord:
    return ClientRecord(
        id=cliente.id,
        empresa_id=empresa_id,
        nome=cliente.nome,
        email=cliente.email,
        telefone=cliente.telefone,
        plano_id=cliente.plano_id,
        assinatura_inicio=_para_utc(cliente.assinatura_inicio),
        assinatura_fim=_para_utc(cliente.assinatura_fim),
        ativo=cliente.ativo,
        credenciais=[
            CredentialRecord(
                empresa_id=empresa_id,
                metodo=item.metodo,
                codigo=item.codigo,
            )
            for item in cliente.credenciais
        ],
    )


def _para_utc(valor: datetime) -> datetime:
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def _empresa(registro: CompanyRecord) -> Empresa:
    return Empresa(
        id=registro.id,
        nome=registro.nome,
        email=registro.email,
        telefone=registro.telefone,
        endereco=registro.endereco,
    )


def _ginasio(registro: GymRecord) -> Ginasio:
    return Ginasio(id=registro.id, nome=registro.nome, endereco=registro.endereco)


def _plano(registro: PlanRecord) -> Plano:
    return Plano(
        id=registro.id,
        nome=registro.nome,
        descricao=registro.descricao,
        max_visitas_semana=registro.max_visitas_semana,
        max_visitas_mes=registro.max_visitas_mes,
        hora_inicio=registro.hora_inicio,
        hora_fim=registro.hora_fim,
        dias_semana=registro.dias_semana,
        duracao_maxima_minutos=registro.duracao_maxima_minutos,
        ginasios_permitidos=registro.ginasios_permitidos,
        ativo=registro.ativo,
    )


def _cliente(registro: ClientRecord) -> Cliente:
    return Cliente(
        id=registro.id,
        nome=registro.nome,
        email=registro.email,
        telefone=registro.telefone,
        plano_id=registro.plano_id,
        assinatura_inicio=_para_utc(registro.assinatura_inicio),
        assinatura_fim=_para_utc(registro.assinatura_fim),
        credenciais=[
            Credencial(metodo=item.metodo, codigo=item.codigo)
            for item in registro.credenciais
        ],
        ativo=registro.ativo,
    )


def _presenca(registro: AttendanceRecord) -> Presenca:
    return Presenca(
        id=registro.id,
        cliente_id=registro.cliente_id,
        ginasio_id=registro.ginasio_id,
        metodo=registro.metodo,
        entrada_em=_para_utc(registro.entrada_em),
        saida_em=None if registro.saida_em is None else _para_utc(registro.saida_em),
    )
