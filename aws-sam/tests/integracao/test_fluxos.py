def vencer(api, nucleo_id, tarefa_id):
    api.tabelas.tarefas.update_item(
        Key={"nucleoId": nucleo_id, "tarefaId": tarefa_id},
        UpdateExpression="SET horarioLimite = :h",
        ExpressionAttributeValues={":h": "2000-01-01T00:00:00+00:00"},
    )


def test_familia_do_cadastro_ao_placar(api):
    assert api.login("ana", "Ana", 30)[0] == 201
    assert api.login("bia", "Bia", 12)[0] == 201

    status, nucleo = api.criar_nucleo("ana", "Família Silva")
    assert status == 201
    assert api.entrar_nucleo("bia", nucleo["nucleoId"])[0] == 200
    assert api.consultar_nucleo("bia", nucleo["nucleoId"])[1]["nome"] == "Família Silva"

    _, louca = api.criar_tarefa("ana", nome="Lavar a louça", pontos=10, idadeMinima=10)
    _, carro = api.criar_tarefa("ana", nome="Lavar o carro", pontos=20, idadeMinima=18)
    assert len(api.listar_tarefas("bia")[1]) == 2

    assert api.escolher("bia", carro["tarefaId"])[0] == 403
    assert api.escolher("bia", louca["tarefaId"])[0] == 200
    assert api.escolher("ana", louca["tarefaId"])[0] == 409
    assert api.concluir("bia", louca["tarefaId"])[0] == 200

    assert api.placar("ana")[1][0]["pontos"] == 0
    assert api.aprovar("bia", louca["tarefaId"])[0] == 403
    assert api.aprovar("ana", louca["tarefaId"])[0] == 200

    _, placar = api.placar("bia")
    assert [(m["nome"], m["pontos"]) for m in placar] == [("Bia", 10), ("Ana", 0)]


def test_rejeicao_e_nova_tentativa(api, familia):
    _, tarefa = api.criar_tarefa("ana", pontos=5)
    tid = tarefa["tarefaId"]
    api.escolher("bia", tid)
    api.concluir("bia", tid)
    assert api.aprovar("ana", tid, aprovado=False)[1]["status"] == "disponivel"

    assert api.escolher("ana", tid)[0] == 200
    api.concluir("ana", tid)
    assert api.aprovar("bia", tid)[0] == 200
    pontos = {m["nome"]: m["pontos"] for m in api.placar("ana")[1]}
    assert pontos == {"Ana": 5, "Bia": 0}


def test_tarefa_sorteada_segue_o_fluxo_normal(api, familia):
    _, tarefa = api.criar_tarefa("ana", idadeMinima=18, pontos=8)
    tid = tarefa["tarefaId"]
    vencer(api, familia, tid)

    assert api.sortear() == {"sorteadas": 1}
    _, lista = api.listar_tarefas("ana", status="em_execucao")
    assert [(t["tarefaId"], t["responsavel"]) for t in lista] == [(tid, "ana")]

    assert api.sortear() == {"sorteadas": 0}
    api.concluir("ana", tid)
    api.aprovar("bia", tid)
    assert api.placar("bia")[1][0] == {"membroId": "ana", "nome": "Ana", "pontos": 8}


def test_familias_nao_se_misturam(api, familia):
    api.login("carla", "Carla", 40)
    _, outro = api.criar_nucleo("carla", "Família Souza")
    _, da_carla = api.criar_tarefa("carla", nome="Da Carla")
    api.criar_tarefa("ana", nome="Da Ana")

    assert [t["nome"] for t in api.listar_tarefas("ana")[1]] == ["Da Ana"]
    assert [t["nome"] for t in api.listar_tarefas("carla")[1]] == ["Da Carla"]
    assert api.escolher("ana", da_carla["tarefaId"])[0] == 404
    assert api.consultar_nucleo("ana", outro["nucleoId"])[0] == 403
    assert api.entrar_nucleo("bia", outro["nucleoId"])[0] == 409
    assert [m["nome"] for m in api.placar("carla")[1]] == ["Carla"]
