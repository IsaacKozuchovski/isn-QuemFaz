import pytest


@pytest.fixture
def concluida(api, familia):
    _, tarefa = api.criar_tarefa("ana", pontos=10)
    api.escolher("bia", tarefa["tarefaId"])
    api.concluir("bia", tarefa["tarefaId"])
    return tarefa["tarefaId"]


def pontos(api, membro):
    return api.login(membro)[1]["pontos"]


def test_aprovar_conclui_e_credita_os_pontos(api, concluida):
    status, tarefa = api.aprovar("ana", concluida)
    assert status == 200
    assert tarefa["status"] == "concluida"
    assert tarefa["aprovadaPor"] == "ana"
    assert pontos(api, "bia") == 10


def test_rn03_quem_fez_nao_aprova(api, concluida):
    assert api.aprovar("bia", concluida)[0] == 403
    assert pontos(api, "bia") == 0


def test_rn04_sem_aprovacao_nao_ha_pontos(api, concluida):
    assert pontos(api, "bia") == 0


def test_rn05_rejeitar_devolve_a_tarefa(api, concluida):
    status, tarefa = api.aprovar("ana", concluida, aprovado=False)
    assert status == 200
    assert tarefa["status"] == "disponivel"
    assert "responsavel" not in tarefa
    assert pontos(api, "bia") == 0


def test_nao_aprova_duas_vezes(api, concluida):
    api.aprovar("ana", concluida)
    assert api.aprovar("ana", concluida)[0] == 409
    assert pontos(api, "bia") == 10


def test_so_aprova_tarefa_aguardando_aprovacao(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    assert api.aprovar("bia", tarefa["tarefaId"])[0] == 409


@pytest.mark.parametrize("corpo", [{}, {"tarefaId": "x"}, {"tarefaId": "x", "aprovado": "sim"}])
def test_corpo_invalido_recebe_400(api, familia, corpo):
    assert api.chamar("aprovar", "POST", "/aprovar", "ana", corpo)[0] == 400


def test_tarefa_inexistente_recebe_404(api, familia):
    assert api.aprovar("ana", "nao-existe")[0] == 404
