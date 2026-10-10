"""Repositório transacional que traduz registros SQLAlchemy para schemas."""

from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.data.database import (
    APP_ENV,
    AdminAccountRecord,
    AttendanceRecord,
    Base,
    ClientRecord,
    CredentialRecord,
    GymRecord,
    PlanRecord,
    SessionLocal,
    engine,
)
from app.models.schemas import Cliente, Credencial, Ginasio, Plano, Presenca


class RegistroDuplicado(Exception):
    pass


class AdministradorJaExiste(Exception):
    pass


class EntradaJaAberta(Exception):
    pass


def novo_id() -> str:
    return uuid4().hex[:12]


def inicializar() -> None:
    """Cria tabelas SQLite e semeia dados de exemplo apenas em desenvolvimento."""
    Base.metadata.create_all(bind=engine)
    if APP_ENV != "development":
        return

    with SessionLocal.begin() as session:
        sem_ginasios = session.scalar(select(func.count()).select_from(GymRecord)) == 0
        sem_planos = session.scalar(select(func.count()).select_from(PlanRecord)) == 0
        sem_clientes = session.scalar(select(func.count()).select_from(ClientRecord)) == 0
        base_vazia = sem_ginasios and sem_planos and sem_clientes

        ginasios = [
            Ginasio(id="gym-centro", nome="Ginásio Centro", endereco="Av. Principal, 100"),
            Ginasio(id="gym-norte", nome="Ginásio Norte", endereco="Rua do Estádio, 12"),
        ]
        for ginasio in ginasios:
            if session.get(GymRecord, ginasio.id) is None:
                session.add(GymRecord(**ginasio.model_dump()))

        planos = [
            Plano(
                id="plano-basico",
                nome="Básico",
                descricao="3 visitas por semana, horário comercial",
                max_visitas_semana=3,
                max_visitas_mes=12,
                hora_inicio=time(8, 0),
                hora_fim=time(18, 0),
                dias_semana=[0, 1, 2, 3, 4, 5],
                duracao_maxima_minutos=90,
                ginasios_permitidos=["gym-centro"],
            ),
            Plano(
                id="plano-premium",
                nome="Premium",
                descricao="Acesso ilimitado aos dois ginásios, qualquer hora",
                dias_semana=[0, 1, 2, 3, 4, 5, 6],
                duracao_maxima_minutos=180,
                ginasios_permitidos=["gym-centro", "gym-norte"],
            ),
            Plano(
                id="plano-night",
                nome="Night",
                descricao="Acesso noturno, 4 visitas por semana",
                max_visitas_semana=4,
                hora_inicio=time(18, 0),
                hora_fim=time(23, 0),
                dias_semana=[0, 1, 2, 3, 4],
                duracao_maxima_minutos=120,
                ginasios_permitidos=["gym-centro", "gym-norte"],
            ),
        ]
        for plano in planos:
            if session.get(PlanRecord, plano.id) is None:
                session.add(PlanRecord(**plano.model_dump()))

        if base_vazia:
            agora = datetime.now(timezone.utc)
            clientes = [
                Cliente(
                    id="cli-joao",
                    nome="João Silva",
                    email="joao@gmail.com",
                    telefone="900000001",
                    plano_id="plano-basico",
                    assinatura_inicio=agora - timedelta(days=10),
                    assinatura_fim=agora + timedelta(days=20),
                    credenciais=[
                        Credencial(metodo="cartao", codigo="CARD-JOAO-001"),
                        Credencial(metodo="pin", codigo="1234"),
                        Credencial(metodo="biometria", codigo="BIO-JOAO-001"),
                    ],
                ),
                Cliente(
                    id="cli-maria",
                    nome="Maria Santos",
                    email="maria@gmail.com",
                    telefone="900000002",
                    plano_id="plano-premium",
                    assinatura_inicio=agora - timedelta(days=5),
                    assinatura_fim=agora + timedelta(days=55),
                    credenciais=[
                        Credencial(metodo="face", codigo="FACE-MARIA-001"),
                        Credencial(metodo="cartao", codigo="CARD-MARIA-001"),
                        Credencial(metodo="qr", codigo="QR-MARIA-001"),
                    ],
                ),
                Cliente(
                    id="cli-pedro",
                    nome="Pedro Costa",
                    email="pedro@gmail.com",
                    telefone="900000003",
                    plano_id="plano-night",
                    assinatura_inicio=agora - timedelta(days=2),
                    assinatura_fim=agora + timedelta(days=28),
                    credenciais=[
                        Credencial(metodo="biometria", codigo="BIO-PEDRO-001"),
                        Credencial(metodo="cartao", codigo="CARD-PEDRO-001"),
                    ],
                ),
            ]
            for cliente in clientes:
                session.add(_registro_cliente(cliente))


def listar_ginasios() -> list[Ginasio]:
    with SessionLocal() as session:
        registros = session.scalars(select(GymRecord).order_by(GymRecord.nome)).all()
        return [_ginasio(registro) for registro in registros]


def obter_ginasio(ginasio_id: str) -> Ginasio | None:
    with SessionLocal() as session:
        registro = session.get(GymRecord, ginasio_id)
        return None if registro is None else _ginasio(registro)


def criar_ginasio(ginasio: Ginasio) -> Ginasio:
    try:
        with SessionLocal.begin() as session:
            session.add(GymRecord(**ginasio.model_dump()))
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return ginasio


def listar_planos() -> list[Plano]:
    with SessionLocal() as session:
        registros = session.scalars(select(PlanRecord).order_by(PlanRecord.nome)).all()
        return [_plano(registro) for registro in registros]


def obter_plano(plano_id: str) -> Plano | None:
    with SessionLocal() as session:
        registro = session.get(PlanRecord, plano_id)
        return None if registro is None else _plano(registro)


def criar_plano(plano: Plano) -> Plano:
    try:
        with SessionLocal.begin() as session:
            session.add(PlanRecord(**plano.model_dump()))
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return plano


def atualizar_plano(plano_id: str, dados: dict) -> Plano | None:
    with SessionLocal.begin() as session:
        registro = session.get(PlanRecord, plano_id)
        if registro is None:
            return None
        for campo, valor in dados.items():
            setattr(registro, campo, valor)
        resultado = _plano(registro)
    return resultado


def listar_clientes() -> list[Cliente]:
    with SessionLocal() as session:
        registros = session.scalars(select(ClientRecord).order_by(ClientRecord.nome)).all()
        return [_cliente(registro) for registro in registros]


def obter_cliente(cliente_id: str) -> Cliente | None:
    with SessionLocal() as session:
        registro = session.get(ClientRecord, cliente_id)
        return None if registro is None else _cliente(registro)


def email_em_uso(email: str) -> bool:
    with SessionLocal() as session:
        return session.scalar(
            select(ClientRecord.id).where(ClientRecord.email == email).limit(1)
        ) is not None


def credenciais_em_uso() -> set[tuple[str, str]]:
    with SessionLocal() as session:
        resultados = session.execute(
            select(CredentialRecord.metodo, CredentialRecord.codigo)
        ).all()
        return {(metodo, codigo) for metodo, codigo in resultados}


def obter_admin_por_email(email: str) -> dict | None:
    with SessionLocal() as session:
        registro = session.scalar(
            select(AdminAccountRecord).where(AdminAccountRecord.email == email)
        )
        if registro is None:
            return None
        return {
            "id": registro.id,
            "email": registro.email,
            "password_hash": registro.password_hash,
            "ativo": registro.ativo,
        }


def admin_ativo(admin_id: str) -> bool:
    with SessionLocal() as session:
        return session.scalar(
            select(AdminAccountRecord.id).where(
                AdminAccountRecord.id == admin_id,
                AdminAccountRecord.ativo.is_(True),
            )
        ) is not None


def criar_primeiro_admin(email: str, password_hash: str) -> str:
    try:
        with SessionLocal.begin() as session:
            total = session.scalar(
                select(func.count()).select_from(AdminAccountRecord)
            )
            if total:
                raise AdministradorJaExiste
            admin_id = novo_id()
            session.add(
                AdminAccountRecord(
                    id=admin_id,
                    email=email,
                    password_hash=password_hash,
                    ativo=True,
                    criado_em=datetime.now(timezone.utc),
                )
            )
        return admin_id
    except IntegrityError as erro:
        raise AdministradorJaExiste from erro


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


def criar_cliente(cliente: Cliente) -> Cliente:
    try:
        with SessionLocal.begin() as session:
            session.add(_registro_cliente(cliente))
    except IntegrityError as erro:
        raise RegistroDuplicado from erro
    return cliente


def atualizar_assinatura(cliente_id: str, dados: dict) -> Cliente | None:
    with SessionLocal.begin() as session:
        registro = session.get(ClientRecord, cliente_id)
        if registro is None:
            return None
        for campo, valor in dados.items():
            if campo in {"assinatura_inicio", "assinatura_fim"}:
                valor = _para_utc(valor)
            setattr(registro, campo, valor)
        resultado = _cliente(registro)
    return resultado


def cliente_por_credencial(metodo: str, codigo: str) -> Cliente | None:
    with SessionLocal() as session:
        registro = session.scalars(
            select(ClientRecord)
            .join(CredentialRecord)
            .where(CredentialRecord.metodo == metodo, CredentialRecord.codigo == codigo)
        ).first()
        return None if registro is None else _cliente(registro)


def presenca_aberta(cliente_id: str) -> Presenca | None:
    with SessionLocal() as session:
        registro = session.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.cliente_id == cliente_id, AttendanceRecord.saida_em.is_(None))
            .order_by(AttendanceRecord.entrada_em.desc())
            .limit(1)
        ).first()
        return None if registro is None else _presenca(registro)


def contar_visitas(cliente_id: str, desde: datetime) -> int:
    with SessionLocal() as session:
        return session.scalar(
            select(func.count()).select_from(AttendanceRecord).where(
                AttendanceRecord.cliente_id == cliente_id,
                AttendanceRecord.entrada_em >= _para_utc(desde),
            )
        ) or 0


def criar_presenca(presenca: Presenca) -> Presenca:
    try:
        with SessionLocal.begin() as session:
            session.add(
                AttendanceRecord(
                    id=presenca.id,
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


def fechar_presenca(presenca_id: str, saida_em: datetime) -> Presenca | None:
    with SessionLocal.begin() as session:
        resultado = session.execute(
            update(AttendanceRecord)
            .where(
                AttendanceRecord.id == presenca_id,
                AttendanceRecord.saida_em.is_(None),
            )
            .values(saida_em=_para_utc(saida_em))
        )
        if resultado.rowcount == 0:
            return None
        registro = session.get(AttendanceRecord, presenca_id)
        resultado = _presenca(registro)
    return resultado


def listar_presencas() -> list[tuple[Presenca, str | None, str | None]]:
    with SessionLocal() as session:
        registros = session.execute(
            select(AttendanceRecord, ClientRecord.nome, GymRecord.nome)
            .outerjoin(ClientRecord, AttendanceRecord.cliente_id == ClientRecord.id)
            .outerjoin(GymRecord, AttendanceRecord.ginasio_id == GymRecord.id)
            .order_by(AttendanceRecord.entrada_em.desc())
        ).all()
        return [(_presenca(presenca), cliente, ginasio) for presenca, cliente, ginasio in registros]


def _registro_cliente(cliente: Cliente) -> ClientRecord:
    return ClientRecord(
        id=cliente.id,
        nome=cliente.nome,
        email=cliente.email,
        telefone=cliente.telefone,
        plano_id=cliente.plano_id,
        assinatura_inicio=_para_utc(cliente.assinatura_inicio),
        assinatura_fim=_para_utc(cliente.assinatura_fim),
        ativo=cliente.ativo,
        credenciais=[
            CredentialRecord(metodo=item.metodo, codigo=item.codigo)
            for item in cliente.credenciais
        ],
    )


def _para_utc(valor: datetime) -> datetime:
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


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
