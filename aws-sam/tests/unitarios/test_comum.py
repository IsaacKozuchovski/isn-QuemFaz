def evento(claims=None, header=None, formato="1.0"):
    autorizador = {}
    if claims:
        autorizador = {"claims": claims} if formato == "1.0" else {"jwt": {"claims": claims}}
    return {
        "requestContext": {"authorizer": autorizador},
        "headers": {"X-Membro-Id": header} if header else {},
    }


def test_token_do_cognito_identifica_pelo_sub(api):
    assert api.tabelas.membro_id(evento(claims={"sub": "abc"})) == "abc"


def test_aceita_claims_no_formato_2_0(api):
    assert api.tabelas.membro_id(evento(claims={"sub": "def"}, formato="2.0")) == "def"


def test_token_vale_mais_que_o_header(api):
    assert api.tabelas.membro_id(evento(claims={"sub": "abc"}, header="falso")) == "abc"


def test_sem_cognito_aceita_header_de_teste(api):
    assert api.tabelas.membro_id(evento(header="ana")) == "ana"


def test_com_exigir_token_ignora_header(api, monkeypatch):
    monkeypatch.setenv("EXIGIR_TOKEN", "1")
    assert api.tabelas.membro_id(evento(header="ana")) is None


def test_sem_identificacao_retorna_401(api):
    status, corpo = api.criar_nucleo(None)
    assert status == 401
