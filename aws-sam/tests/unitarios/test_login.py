def test_primeiro_acesso_cria_membro(api):
    status, membro = api.login("ana", "Ana", 30)
    assert status == 201
    assert membro == {"membroId": "ana", "nome": "Ana", "email": "ana@teste", "idade": 30, "pontos": 0}


def test_login_de_novo_devolve_o_cadastro(api):
    api.login("ana", "Ana", 30)
    status, membro = api.login("ana")
    assert status == 200
    assert membro["nome"] == "Ana"


def test_membro_novo_sem_nome_e_idade_recebe_400(api):
    status, _ = api.login("ana")
    assert status == 400


def test_idade_negativa_ou_nao_inteira_e_recusada(api):
    assert api.login("ana", "Ana", -1)[0] == 400
    assert api.login("ana", "Ana", "30")[0] == 400


def test_email_vem_do_token_e_nao_do_formulario(api):
    evento = {
        "httpMethod": "POST",
        "resource": "/login",
        "headers": {},
        "requestContext": {"authorizer": {"claims": {"sub": "g-123", "email": "real@gmail.com"}}},
        "body": '{"nome": "Ana", "idade": 30, "email": "falso@teste"}',
    }
    r = api.handler("login").handler(evento, None)
    assert r["statusCode"] == 201
    assert '"email": "real@gmail.com"' in r["body"]
