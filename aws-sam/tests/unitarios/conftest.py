import boto3
import pytest
from moto import mock_aws

from apoio import Api, criar_tabelas


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "sa-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "teste")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "teste")
    monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)
    monkeypatch.delenv("EXIGIR_TOKEN", raising=False)
    monkeypatch.delenv("REMETENTE", raising=False)
    with mock_aws():
        nomes = criar_tabelas(boto3.client("dynamodb"))
        for variavel, nome in nomes.items():
            monkeypatch.setenv(variavel, nome)
        yield Api()
