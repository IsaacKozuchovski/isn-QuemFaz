def test_placar_ordenado_por_pontos(api, familia):
    _, tarefa = api.criar_tarefa("ana", pontos=7)
    api.escolher("bia", tarefa["tarefaId"])
    api.concluir("bia", tarefa["tarefaId"])
    api.aprovar("ana", tarefa["tarefaId"])
    status, placar = api.placar("ana")
    assert status == 200
    assert [(m["nome"], m["pontos"]) for m in placar] == [("Bia", 7), ("Ana", 0)]


def test_placar_so_mostra_o_proprio_nucleo(api, familia):
    api.login("carla", "Carla", 40)
    api.criar_nucleo("carla", "Outra")
    _, placar = api.placar("carla")
    assert [m["nome"] for m in placar] == ["Carla"]


def test_rn07_sem_nucleo_nao_ve_placar(api):
    api.login("carla", "Carla", 40)
    assert api.placar("carla")[0] == 403
