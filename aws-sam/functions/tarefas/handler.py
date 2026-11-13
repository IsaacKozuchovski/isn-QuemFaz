"""Tarefas do núcleo do membro autenticado.

UC04 · POST /tarefas                     cadastra tarefa
       GET  /tarefas[?status=...]        lista tarefas do núcleo
UC05 · POST /tarefas/{tarefaId}/escolher assume a tarefa
UC07 · POST /tarefas/{tarefaId}/concluir marca como concluída (aguarda aprovação)
"""
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from comum import corpo, erro, membro_atual, resposta, tarefas

DISPONIVEL = "disponivel"
EM_EXECUCAO = "em_execucao"
AGUARDANDO = "aguardando_aprovacao"


def _agora():
    return datetime.now(timezone.utc)


def _data(texto):
    """Converte ISO 8601 (ex.: 2026-10-20T18:00:00Z) para datetime com fuso, ou None."""
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return data if data.tzinfo else None


def listar(event, membro):
    filtro = (event.get("queryStringParameters") or {}).get("status")
    params = {"KeyConditionExpression": Key("nucleoId").eq(membro["nucleoId"])}
    if filtro:
        params["FilterExpression"] = Attr("status").eq(filtro)
    return resposta(200, tarefas.query(**params)["Items"])


def criar(event, membro):
    dados = corpo(event)
    if dados is None:
        return erro(400, "JSON inválido")

    pontos, idade_minima = dados.get("pontos"), dados.get("idadeMinima", 0)
    limite = _data(dados.get("horarioLimite"))
    if not dados.get("nome") or not isinstance(pontos, int) or pontos <= 0:
        return erro(400, "nome e pontos (inteiro positivo) são obrigatórios")
    if not isinstance(idade_minima, int) or idade_minima < 0:
        return erro(400, "idadeMinima deve ser um inteiro >= 0")
    if not limite:
        return erro(400, "horarioLimite deve estar em ISO 8601 com fuso (ex.: 2026-10-20T18:00:00Z)")
    if limite <= _agora():
        return erro(400, "horarioLimite já passou")
    descricao = dados.get("descricao") or ""
    if not isinstance(descricao, str) or len(descricao) > 500:
        return erro(400, "descricao deve ser um texto de até 500 caracteres")

    tarefa = {
        "nucleoId": membro["nucleoId"],
        "tarefaId": str(uuid.uuid4()),
        "nome": dados["nome"],
        "descricao": descricao.strip(),
        "pontos": pontos,
        "idadeMinima": idade_minima,
        "horarioLimite": limite.isoformat(),
        "status": DISPONIVEL,
        "criadaPor": membro["membroId"],
    }
    tarefas.put_item(Item=tarefa)
    return resposta(201, tarefa)


def _buscar(membro, tarefa_id):
    return tarefas.get_item(Key={"nucleoId": membro["nucleoId"], "tarefaId": tarefa_id}).get("Item")


def escolher(membro, tarefa_id):
    tarefa = _buscar(membro, tarefa_id)
    if not tarefa:
        return erro(404, "Tarefa não encontrada")
    if membro["idade"] < tarefa["idadeMinima"]:  # RN01
        return erro(403, "Você não atende à idade mínima desta tarefa")
    if _data(tarefa["horarioLimite"]) <= _agora():
        return erro(409, "O horário-limite desta tarefa já passou")

    try:
        # A condição evita que dois membros escolham a mesma tarefa ao mesmo tempo
        atualizada = tarefas.update_item(
            Key={"nucleoId": membro["nucleoId"], "tarefaId": tarefa_id},
            UpdateExpression="SET #s = :novo, responsavel = :m",
            ConditionExpression="#s = :disp",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":novo": EM_EXECUCAO, ":m": membro["membroId"], ":disp": DISPONIVEL},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return erro(409, "Tarefa não está mais disponível")
        raise
    return resposta(200, atualizada)


def concluir(membro, tarefa_id):
    try:
        atualizada = tarefas.update_item(
            Key={"nucleoId": membro["nucleoId"], "tarefaId": tarefa_id},
            UpdateExpression="SET #s = :novo",
            ConditionExpression="#s = :exec AND responsavel = :m",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":novo": AGUARDANDO, ":exec": EM_EXECUCAO, ":m": membro["membroId"]},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return erro(409, "A tarefa precisa estar em execução e atribuída a você")
        raise
    return resposta(200, atualizada)


def handler(event, context):
    membro, falha = membro_atual(event)
    if falha:
        return falha
    if not membro.get("nucleoId"):  # RN07
        return erro(403, "Você não pertence a nenhum núcleo familiar")

    # "resource" é a rota declarada no template, ex.: /tarefas/{tarefaId}/escolher
    rota = event["resource"]
    tarefa_id = (event.get("pathParameters") or {}).get("tarefaId")
    if rota.endswith("/escolher"):
        return escolher(membro, tarefa_id)
    if rota.endswith("/concluir"):
        return concluir(membro, tarefa_id)
    if event["httpMethod"] == "GET":
        return listar(event, membro)
    return criar(event, membro)
