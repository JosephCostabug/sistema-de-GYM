"""Regras de autorização de entrada e cálculo de utilização dos planos."""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.data import store
from app.data.store import EntradaJaAberta
from app.models.schemas import Cliente, MetodoAcesso, Plano, Presenca


class AcessoNegado(Exception):
    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)


def encontrar_cliente(metodo: MetodoAcesso, credencial: str) -> Cliente:
    codigo = credencial.strip()
    cliente = store.cliente_por_credencial(metodo, codigo)
    if cliente is not None:
        return cliente
    raise AcessoNegado("Credencial não reconhecida. Verifique o método e o código.")


def plano_do_cliente(cliente: Cliente) -> Plano:
    plano = store.obter_plano(cliente.plano_id)
    if plano is not None:
        return plano
    raise AcessoNegado("O cliente não tem um plano associado.")


def presenca_aberta(cliente_id: str) -> Presenca | None:
    return store.presenca_aberta(cliente_id)


def _inicio_semana(momento: datetime) -> datetime:
    inicio = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    return inicio - timedelta(days=inicio.weekday())


def _inicio_mes(momento: datetime) -> datetime:
    return momento.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def contar_visitas(cliente_id: str, desde: datetime) -> int:
    return store.contar_visitas(cliente_id, desde)


def uso_do_plano(cliente: Cliente, plano: Plano, agora: datetime) -> dict[str, Any]:
    visitas_semana = contar_visitas(cliente.id, _inicio_semana(agora))
    visitas_mes = contar_visitas(cliente.id, _inicio_mes(agora))
    return {
        "visitas_semana": visitas_semana,
        "max_visitas_semana": plano.max_visitas_semana,
        "restantes_semana": None
        if plano.max_visitas_semana is None
        else max(plano.max_visitas_semana - visitas_semana, 0),
        "visitas_mes": visitas_mes,
        "max_visitas_mes": plano.max_visitas_mes,
        "restantes_mes": None
        if plano.max_visitas_mes is None
        else max(plano.max_visitas_mes - visitas_mes, 0),
        "horario": {
            "inicio": None if plano.hora_inicio is None else plano.hora_inicio.strftime("%H:%M"),
            "fim": None if plano.hora_fim is None else plano.hora_fim.strftime("%H:%M"),
        },
        "dias_semana": plano.dias_semana,
        "duracao_maxima_minutos": plano.duracao_maxima_minutos,
    }


def validar_entrada(cliente: Cliente, plano: Plano, ginasio_id: str, agora: datetime) -> None:
    if not cliente.ativo:
        raise AcessoNegado("Cliente inativo.")
    if not plano.ativo:
        raise AcessoNegado("O plano deste cliente está inativo.")
    if agora < cliente.assinatura_inicio or agora > cliente.assinatura_fim:
        raise AcessoNegado("Assinatura expirada ou ainda não iniciada.")
    if plano.ginasios_permitidos and ginasio_id not in plano.ginasios_permitidos:
        raise AcessoNegado("O plano não permite acesso a este ginásio.")
    if agora.weekday() not in plano.dias_semana:
        raise AcessoNegado("O plano não permite acesso neste dia da semana.")
    hora = agora.time().replace(tzinfo=None, microsecond=0)
    if plano.hora_inicio and hora < plano.hora_inicio:
        raise AcessoNegado(
            f"Acesso só a partir das {plano.hora_inicio.strftime('%H:%M')} com este plano."
        )
    if plano.hora_fim and hora > plano.hora_fim:
        raise AcessoNegado(
            f"Acesso só até às {plano.hora_fim.strftime('%H:%M')} com este plano."
        )
    if presenca_aberta(cliente.id):
        raise AcessoNegado("Já existe uma entrada aberta. Marque a saída primeiro.")

    uso = uso_do_plano(cliente, plano, agora)
    if plano.max_visitas_semana is not None and uso["visitas_semana"] >= plano.max_visitas_semana:
        raise AcessoNegado("Limite semanal de visitas do plano já foi atingido.")
    if plano.max_visitas_mes is not None and uso["visitas_mes"] >= plano.max_visitas_mes:
        raise AcessoNegado("Limite mensal de visitas do plano já foi atingido.")


def marcar(
    ginasio_id: str,
    metodo: MetodoAcesso,
    credencial: str,
    tipo: str | None,
) -> dict[str, Any]:
    """Regista uma entrada ou fecha a presença aberta do cliente."""
    agora = datetime.now(timezone.utc)
    ginasio = store.obter_ginasio(ginasio_id)
    if ginasio is None:
        raise AcessoNegado("Ginásio não encontrado.")

    cliente = encontrar_cliente(metodo, credencial)
    plano = plano_do_cliente(cliente)
    aberta = presenca_aberta(cliente.id)

    if tipo is None:
        tipo = "saida" if aberta else "entrada"

    if tipo == "entrada":
        validar_entrada(cliente, plano, ginasio_id, agora)
        presenca = Presenca(
            id=store.novo_id(),
            cliente_id=cliente.id,
            ginasio_id=ginasio_id,
            metodo=metodo,
            entrada_em=agora,
        )
        try:
            store.criar_presenca(presenca)
        except EntradaJaAberta as erro:
            raise AcessoNegado(
                "Já existe uma entrada aberta. Marque a saída primeiro."
            ) from erro
        uso = uso_do_plano(cliente, plano, agora)
        return {
            "autorizado": True,
            "tipo": "entrada",
            "mensagem": f"Entrada registada. Bem-vindo, {cliente.nome}.",
            "cliente": cliente.nome,
            "plano": plano.nome,
            "ginasio": ginasio.nome,
            "metodo": metodo,
            "entrada_em": presenca.entrada_em.isoformat(timespec="seconds"),
            "uso_plano": uso,
        }

    if tipo == "saida":
        if aberta is None:
            raise AcessoNegado("Não há entrada aberta para marcar saída.")
        fechada = store.fechar_presenca(aberta.id, agora)
        if fechada is None:
            raise AcessoNegado("A entrada não está mais aberta.")
        minutos = int((fechada.saida_em - fechada.entrada_em).total_seconds() // 60)
        aviso = None
        if plano.duracao_maxima_minutos and minutos > plano.duracao_maxima_minutos:
            aviso = (
                f"Sessão de {minutos} min acima do limite do plano "
                f"({plano.duracao_maxima_minutos} min)."
            )
        return {
            "autorizado": True,
            "tipo": "saida",
            "mensagem": f"Saída registada. Até breve, {cliente.nome}.",
            "cliente": cliente.nome,
            "plano": plano.nome,
            "ginasio": ginasio.nome,
            "metodo": metodo,
            "entrada_em": fechada.entrada_em.isoformat(timespec="seconds"),
            "saida_em": fechada.saida_em.isoformat(timespec="seconds"),
            "duracao_minutos": minutos,
            "aviso": aviso,
            "uso_plano": uso_do_plano(cliente, plano, agora),
        }

    raise AcessoNegado("Tipo de marcação inválido. Use entrada ou saida.")
