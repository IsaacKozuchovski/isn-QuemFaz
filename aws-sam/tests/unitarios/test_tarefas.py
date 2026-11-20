import pytest


def test_criar_tarefa(api, familia):
    status, tarefa = api.criar_tarefa("ana", nome="Varrer", pontos=5, idadeMinima=10, descricao="  sala  ")
    assert status == 201
    assert tarefa["status"] == "disponivel"
    assert tarefa["nucleoId"] == familia
    assert tarefa["descricao"] == "sala"
    assert tarefa["horarioLimite"] == "2099-01-01T18:00:00+00:00"


@pytest.mark.parametrize(
    "campos",
    [
        {"nome": ""},
        {"pontos": 0},
        {"pontos": "10"},
        {"idadeMinima": -1},
        {"horarioLimite": "amanhã"},
        {"horarioLimite": "2099-01-01T18:00:00"},
        {"horarioLimite": "2000-01-01T18:00:00Z"},
        {"descricao": "x" * 501},
    ],
)
def test_criar_tarefa_invalida_recebe_400(api, familia, campos):
    assert api.criar_tarefa("ana", **campos)[0] == 400


def test_rn07_sem_nucleo_nao_cria_nem_lista(api):
    api.login("carla", "Carla", 40)
    assert api.criar_tarefa("carla")[0] == 403
    assert api.listar_tarefas("carla")[0] == 403


def test_lista_so_as_tarefas_do_proprio_nucleo(api, familia):
    api.criar_tarefa("ana", nome="Da família")
    api.login("carla", "Carla", 40)
    api.criar_nucleo("carla", "Outra")
    api.criar_tarefa("carla", nome="De outra família")
    _, lista = api.listar_tarefas("bia")
    assert [t["nome"] for t in lista] == ["Da família"]


def test_listar_filtrando_por_status(api, familia):
    _, t1 = api.criar_tarefa("ana", nome="A")
    api.criar_tarefa("ana", nome="B")
    api.escolher("ana", t1["tarefaId"])
    _, lista = api.listar_tarefas("ana", status="em_execucao")
    assert [t["nome"] for t in lista] == ["A"]


def test_escolher_tarefa(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    status, escolhida = api.escolher("bia", tarefa["tarefaId"])
    assert status == 200
    assert escolhida["status"] == "em_execucao"
    assert escolhida["responsavel"] == "bia"


def test_rn01_idade_minima_para_escolher(api, familia):
    _, tarefa = api.criar_tarefa("ana", idadeMinima=18)
    assert api.escolher("bia", tarefa["tarefaId"])[0] == 403
    assert api.escolher("ana", tarefa["tarefaId"])[0] == 200


def test_tarefa_ja_escolhida_nao_pode_ser_escolhida_de_novo(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    api.escolher("ana", tarefa["tarefaId"])
    assert api.escolher("bia", tarefa["tarefaId"])[0] == 409


def test_nao_escolhe_depois_do_horario_limite(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    chave = {"nucleoId": familia, "tarefaId": tarefa["tarefaId"]}
    api.tabelas.tarefas.update_item(
        Key=chave,
        UpdateExpression="SET horarioLimite = :h",
        ExpressionAttributeValues={":h": "2000-01-01T00:00:00+00:00"},
    )
    assert api.escolher("bia", tarefa["tarefaId"])[0] == 409


def test_escolher_tarefa_inexistente_recebe_404(api, familia):
    assert api.escolher("ana", "nao-existe")[0] == 404


def test_concluir_vai_para_aguardando_aprovacao(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    api.escolher("bia", tarefa["tarefaId"])
    status, concluida = api.concluir("bia", tarefa["tarefaId"])
    assert status == 200
    assert concluida["status"] == "aguardando_aprovacao"


def test_so_o_responsavel_conclui(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    assert api.concluir("ana", tarefa["tarefaId"])[0] == 409
    api.escolher("bia", tarefa["tarefaId"])
    assert api.concluir("ana", tarefa["tarefaId"])[0] == 409
