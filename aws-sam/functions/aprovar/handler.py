"""UC08 · POST /aprovar: aprova ou rejeita a conclusão de uma tarefa.

Body: {"tarefaId": "...", "aprovado": true | false}
"""
from botocore.exceptions import ClientError

from comum import corpo, erro, membro_atual, membros, resposta, tarefas


def handler(event, context):
    membro, falha = membro_atual(event)
    if falha:
        return falha
    if not membro.get("nucleoId"):  # RN07
        return erro(403, "Você não pertence a nenhum núcleo familiar")

    dados = corpo(event)
    if not dados or not dados.get("tarefaId") or not isinstance(dados.get("aprovado"), bool):
        return erro(400, "tarefaId e aprovado (true/false) são obrigatórios")

    chave = {"nucleoId": membro["nucleoId"], "tarefaId": dados["tarefaId"]}
    tarefa = tarefas.get_item(Key=chave).get("Item")
    if not tarefa:
        return erro(404, "Tarefa não encontrada")
    if tarefa["status"] != "aguardando_aprovacao":
        return erro(409, "Tarefa não está aguardando aprovação")
    if tarefa["responsavel"] == membro["membroId"]:  # RN03
        return erro(403, "Quem executou a tarefa não pode aprová-la")

    if dados["aprovado"]:
        update = "SET #s = :concluida, aprovadaPor = :m"
        valores = {":concluida": "concluida", ":m": membro["membroId"]}
    else:  # RN05
        update = "SET #s = :disp REMOVE responsavel"
        valores = {":disp": "disponivel"}

    try:
        atualizada = tarefas.update_item(
            Key=chave,
            UpdateExpression=update,
            ConditionExpression="#s = :aguardando",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={**valores, ":aguardando": "aguardando_aprovacao"},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return erro(409, "Tarefa não está aguardando aprovação")
        raise

    if dados["aprovado"]:  # RN04: pontos só entram após a aprovação
        membros.update_item(
            Key={"membroId": tarefa["responsavel"]},
            UpdateExpression="ADD pontos :p",
            ExpressionAttributeValues={":p": tarefa["pontos"]},
        )

    return resposta(200, atualizada)
