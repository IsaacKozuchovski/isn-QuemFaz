"""UC02 · POST /nucleos: cria o núcleo familiar.
UC03 · POST /nucleos/{nucleoId}/membros: entra num núcleo (o id funciona como convite).
"""
import uuid

from botocore.exceptions import ClientError

from comum import corpo, erro, membro_atual, membros, nucleos, resposta


def _vincular(membro, nucleo_id):
    """Vincula o membro ao núcleo, só se ele ainda não tiver um (RN06)."""
    try:
        membros.update_item(
            Key={"membroId": membro["membroId"]},
            UpdateExpression="SET nucleoId = :n",
            ConditionExpression="attribute_not_exists(nucleoId)",
            ExpressionAttributeValues={":n": nucleo_id},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def criar(event, membro):
    dados = corpo(event)
    if not dados or not dados.get("nome"):
        return erro(400, "nome é obrigatório")

    nucleo = {"nucleoId": str(uuid.uuid4()), "nome": dados["nome"], "criadoPor": membro["membroId"]}
    if not _vincular(membro, nucleo["nucleoId"]):
        return erro(409, "Você já pertence a um núcleo familiar")
    nucleos.put_item(Item=nucleo)
    return resposta(201, nucleo)


def entrar(event, membro):
    nucleo_id = event["pathParameters"]["nucleoId"]
    nucleo = nucleos.get_item(Key={"nucleoId": nucleo_id}).get("Item")
    if not nucleo:
        return erro(404, "Convite inválido")
    if not _vincular(membro, nucleo_id):
        return erro(409, "Você já pertence a um núcleo familiar")
    return resposta(200, nucleo)


def handler(event, context):
    membro, falha = membro_atual(event)
    if falha:
        return falha
    if event.get("pathParameters"):
        return entrar(event, membro)
    return criar(event, membro)
