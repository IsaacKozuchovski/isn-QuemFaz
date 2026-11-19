"""UC06 · Sorteio automático (RN02), chamado pelo EventBridge Scheduler.

Procura tarefas "disponível" cujo horário-limite já passou e sorteia um
membro do núcleo com a idade mínima (RN01). Se ninguém for elegível, a
tarefa continua disponível (fluxo alternativo do UC06). O sorteado recebe
um email (SES) quando REMETENTE está configurado.
"""
import os
import random
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from comum import membros, nucleos, tarefas

REMETENTE = os.environ.get("REMETENTE")
SITE_URL = os.environ.get("SITE_URL", "")
ses = boto3.client("sesv2") if REMETENTE else None


def _vencida(tarefa, agora):
    try:
        limite = datetime.fromisoformat(tarefa["horarioLimite"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    return limite.tzinfo is not None and limite <= agora


def _tarefas_vencidas(agora):
    params = {"FilterExpression": Attr("status").eq("disponivel")}
    while True:
        pagina = tarefas.scan(**params)
        for tarefa in pagina["Items"]:
            if _vencida(tarefa, agora):
                yield tarefa
        if "LastEvaluatedKey" not in pagina:
            return
        params["ExclusiveStartKey"] = pagina["LastEvaluatedKey"]


def _atribuir(tarefa, membro):
    """Atribui só se a tarefa ainda estiver disponível (alguém pode ter escolhido)."""
    try:
        tarefas.update_item(
            Key={"nucleoId": tarefa["nucleoId"], "tarefaId": tarefa["tarefaId"]},
            UpdateExpression="SET #s = :exec, responsavel = :m, sorteada = :t",
            ConditionExpression="#s = :disp",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":exec": "em_execucao",
                ":m": membro["membroId"],
                ":t": True,
                ":disp": "disponivel",
            },
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _avisar(tarefa, membro):
    """Email para o sorteado. Uma falha no envio não desfaz o sorteio."""
    email = membro.get("email")
    if not email:
        print(f"Sem email para avisar {membro['membroId']}")
        return
    if not ses:
        print(f"(sem REMETENTE) avisaria {email} sobre a tarefa {tarefa['nome']}")
        return

    nucleo = nucleos.get_item(Key={"nucleoId": tarefa["nucleoId"]}).get("Item") or {}
    familia = nucleo.get("nome", "sua família")
    texto = (
        f"Olá, {membro['nome']}!\n\n"
        f"Ninguém escolheu a tarefa \"{tarefa['nome']}\" ({familia}) até o horário-limite, "
        f"e você foi sorteado(a) para fazê-la. Ela vale {tarefa['pontos']} pontos.\n\n"
        f"Quando terminar, marque como concluída no QuemFaz: {SITE_URL}\n"
    )
    try:
        ses.send_email(
            FromEmailAddress=f"QuemFaz <{REMETENTE}>",
            Destination={"ToAddresses": [email]},
            Content={
                "Simple": {
                    "Subject": {"Data": f"Você foi sorteado(a): {tarefa['nome']}", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": texto, "Charset": "UTF-8"}},
                }
            },
        )
        print(f"Email enviado para {email}")
    except ClientError as e:
        # No sandbox do SES, destinatários não verificados são recusados
        print(f"Falha ao enviar email para {email}: {e.response['Error']['Message']}")


def handler(event, context):
    agora = datetime.now(timezone.utc)
    sorteadas = 0
    for tarefa in _tarefas_vencidas(agora):
        familia = membros.query(
            IndexName="nucleoId-index",
            KeyConditionExpression=Key("nucleoId").eq(tarefa["nucleoId"]),
        )["Items"]
        elegiveis = [m for m in familia if m.get("idade", 0) >= tarefa.get("idadeMinima", 0)]  # RN01
        if not elegiveis:
            print(f"Tarefa {tarefa['tarefaId']}: ninguém elegível, continua disponível")
            continue
        sorteado = random.choice(elegiveis)
        if _atribuir(tarefa, sorteado):
            sorteadas += 1
            print(f"Tarefa {tarefa['tarefaId']} sorteada para {sorteado['membroId']}")
            _avisar(tarefa, sorteado)
    return {"sorteadas": sorteadas}
