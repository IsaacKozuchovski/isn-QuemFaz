def test_criar_nucleo_vincula_o_criador(api):
    api.login("ana", "Ana", 30)
    status, nucleo = api.criar_nucleo("ana", "Família Silva")
    assert status == 201
    assert nucleo["nome"] == "Família Silva"
    assert api.login("ana")[1]["nucleoId"] == nucleo["nucleoId"]


def test_criar_nucleo_sem_nome_recebe_400(api):
    api.login("ana", "Ana", 30)
    assert api.chamar("nucleos", "POST", "/nucleos", "ana", {})[0] == 400


def test_membro_nao_cadastrado_recebe_404(api):
    assert api.criar_nucleo("fantasma")[0] == 404


def test_entrar_com_convite(api, familia):
    assert api.login("bia")[1]["nucleoId"] == familia


def test_convite_invalido_recebe_404(api):
    api.login("bia", "Bia", 12)
    assert api.entrar_nucleo("bia", "nao-existe")[0] == 404


def test_rn06_um_nucleo_por_membro(api, familia):
    assert api.criar_nucleo("ana")[0] == 409
    api.login("carla", "Carla", 40)
    _, outro = api.criar_nucleo("carla", "Outra família")
    assert api.entrar_nucleo("bia", outro["nucleoId"])[0] == 409


def test_consultar_o_proprio_nucleo(api, familia):
    status, nucleo = api.consultar_nucleo("bia", familia)
    assert status == 200
    assert nucleo["nome"] == "Família Teste"


def test_rn07_nao_ve_nucleo_dos_outros(api, familia):
    api.login("carla", "Carla", 40)
    assert api.consultar_nucleo("carla", familia)[0] == 403
