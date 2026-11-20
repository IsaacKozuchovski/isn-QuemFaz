import json
import os
from decimal import Decimal

import boto3

_endpoint = os.environ.get("DYNAMODB_ENDPOINT") or None
_local = {"aws_access_key_id": "local", "aws_secret_access_key": "local"} if _endpoint else {}

dynamodb = boto3.resource("dynamodb", endpoint_url=_endpoint, **_local)

membros = dynamodb.Table(os.environ["MEMBROS_TABLE"])
nucleos = dynamodb.Table(os.environ["NUCLEOS_TABLE"])
tarefas = dynamodb.Table(os.environ["TAREFAS_TABLE"])


def _decimal(valor):
    return int(valor) if valor % 1 == 0 else float(valor)


def resposta(status, corpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo, default=_decimal, ensure_ascii=False),
    }


def erro(status, mensagem):
    return resposta(status, {"message": mensagem})


def corpo(event):
    try:
        dados = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None
    return dados if isinstance(dados, dict) else None


def claims(event):
    autorizador = (event.get("requestContext") or {}).get("authorizer") or {}
    return autorizador.get("claims") or (autorizador.get("jwt") or {}).get("claims") or {}


def membro_id(event):
    sub = claims(event).get("sub")
    if sub or os.environ.get("EXIGIR_TOKEN"):
        return sub
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    return headers.get("x-membro-id")


def membro_atual(event):
    mid = membro_id(event)
    if not mid:
        return None, erro(401, "Usuário não identificado")
    membro = membros.get_item(Key={"membroId": mid}).get("Item")
    if not membro:
        return None, erro(404, "Membro não cadastrado; faça login primeiro")
    return membro, None
