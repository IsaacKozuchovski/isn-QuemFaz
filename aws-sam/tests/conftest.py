import pytest


@pytest.fixture
def familia(api):
    api.login("ana", "Ana", 30)
    api.login("bia", "Bia", 12)
    _, nucleo = api.criar_nucleo("ana")
    api.entrar_nucleo("bia", nucleo["nucleoId"])
    return nucleo["nucleoId"]
