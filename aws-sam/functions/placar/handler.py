"""UC09 · GET /placar: pontuação dos membros do núcleo, do maior para o menor."""
from boto3.dynamodb.conditions import Key

from comum import erro, membro_atual, membros, resposta


def handler(event, context):
    membro, falha = membro_atual(event)
    if falha:
        return falha
    if not membro.get("nucleoId"):  # RN07
        return erro(403, "Você não pertence a nenhum núcleo familiar")

    itens = membros.query(
        IndexName="nucleoId-index",
        KeyConditionExpression=Key("nucleoId").eq(membro["nucleoId"]),
    )["Items"]

    placar = sorted(
        ({"membroId": m["membroId"], "nome": m["nome"], "pontos": m.get("pontos", 0)} for m in itens),
        key=lambda m: m["pontos"],
        reverse=True,
    )
    return resposta(200, placar)
