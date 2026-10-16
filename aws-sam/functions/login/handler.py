"""UC01 · POST /login: cria ou recupera o membro autenticado."""
from comum import corpo, erro, membro_id, membros, resposta


def handler(event, context):
    mid = membro_id(event)
    if not mid:
        return erro(401, "Usuário não identificado")

    existente = membros.get_item(Key={"membroId": mid}).get("Item")
    if existente:
        return resposta(200, existente)

    dados = corpo(event)
    if dados is None:
        return erro(400, "JSON inválido")
    idade = dados.get("idade")
    if not dados.get("nome") or type(idade) is not int or idade < 0:
        return erro(400, "nome e idade (inteiro >= 0) são obrigatórios")

    membro = {
        "membroId": mid,
        "nome": dados["nome"],
        "email": dados.get("email", ""),
        "idade": dados["idade"],
        "pontos": 0,
    }
    membros.put_item(Item=membro)
    return resposta(201, membro)
