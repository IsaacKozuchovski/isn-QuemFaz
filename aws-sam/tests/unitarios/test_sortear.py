def vencer(api, nucleo_id, tarefa_id):
    api.tabelas.tarefas.update_item(
        Key={"nucleoId": nucleo_id, "tarefaId": tarefa_id},
        UpdateExpression="SET horarioLimite = :h",
        ExpressionAttributeValues={":h": "2000-01-01T00:00:00+00:00"},
    )


def buscar(api, nucleo_id, tarefa_id):
    return api.tabelas.tarefas.get_item(Key={"nucleoId": nucleo_id, "tarefaId": tarefa_id})["Item"]


class SesFalso:
    def __init__(self):
        self.enviados = []

    def send_email(self, **kwargs):
        self.enviados.append(kwargs)


def test_rn02_sorteia_tarefa_vencida(api, familia):
    _, tarefa = api.criar_tarefa("ana")
    vencer(api, familia, tarefa["tarefaId"])
    assert api.sortear() == {"sorteadas": 1}
    sorteada = buscar(api, familia, tarefa["tarefaId"])
    assert sorteada["status"] == "em_execucao"
    assert sorteada["responsavel"] in ("ana", "bia")
    assert sorteada["sorteada"] is True


def test_rn01_so_sorteia_quem_tem_a_idade_minima(api, familia):
    for _ in range(10):
        _, tarefa = api.criar_tarefa("ana", idadeMinima=18)
        vencer(api, familia, tarefa["tarefaId"])
    api.sortear()
    _, lista = api.listar_tarefas("ana")
    assert {t["responsavel"] for t in lista} == {"ana"}


def test_ninguem_elegivel_continua_disponivel(api, familia):
    _, tarefa = api.criar_tarefa("ana", idadeMinima=99)
    vencer(api, familia, tarefa["tarefaId"])
    assert api.sortear() == {"sorteadas": 0}
    assert buscar(api, familia, tarefa["tarefaId"])["status"] == "disponivel"


def test_nao_mexe_em_tarefa_no_prazo_ou_ja_escolhida(api, familia):
    _, futura = api.criar_tarefa("ana", nome="Futura")
    _, escolhida = api.criar_tarefa("ana", nome="Escolhida")
    api.escolher("bia", escolhida["tarefaId"])
    vencer(api, familia, escolhida["tarefaId"])
    assert api.sortear() == {"sorteadas": 0}
    assert buscar(api, familia, futura["tarefaId"])["status"] == "disponivel"
    assert buscar(api, familia, escolhida["tarefaId"])["responsavel"] == "bia"


def test_envia_email_para_o_sorteado(api, familia, monkeypatch):
    monkeypatch.setenv("REMETENTE", "nao-responda@quemfaz.negoci.online")
    monkeypatch.setenv("SITE_URL", "https://quemfaz.negoci.online")
    sortear = api.handler("sortear")
    ses = SesFalso()
    monkeypatch.setattr(sortear, "ses", ses)
    monkeypatch.setattr(sortear, "REMETENTE", "nao-responda@quemfaz.negoci.online")
    monkeypatch.setattr(sortear, "SITE_URL", "https://quemfaz.negoci.online")

    _, tarefa = api.criar_tarefa("ana", nome="Lavar a louça", idadeMinima=18)
    vencer(api, familia, tarefa["tarefaId"])
    api.sortear()

    assert len(ses.enviados) == 1
    email = ses.enviados[0]
    assert email["Destination"] == {"ToAddresses": ["ana@teste"]}
    assert email["FromEmailAddress"] == "QuemFaz <nao-responda@quemfaz.negoci.online>"
    assert "Lavar a louça" in email["Content"]["Simple"]["Subject"]["Data"]
    texto = email["Content"]["Simple"]["Body"]["Text"]["Data"]
    assert "Família Teste" in texto and "https://quemfaz.negoci.online" in texto


def test_falha_no_email_nao_desfaz_o_sorteio(api, familia, monkeypatch):
    from botocore.exceptions import ClientError

    class SesQuebrado:
        def send_email(self, **kwargs):
            raise ClientError({"Error": {"Code": "MessageRejected", "Message": "não verificado"}}, "SendEmail")

    sortear = api.handler("sortear")
    monkeypatch.setattr(sortear, "ses", SesQuebrado())
    _, tarefa = api.criar_tarefa("ana")
    vencer(api, familia, tarefa["tarefaId"])
    assert api.sortear() == {"sorteadas": 1}
    assert buscar(api, familia, tarefa["tarefaId"])["status"] == "em_execucao"
