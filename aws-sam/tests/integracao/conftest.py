import os
import time
import uuid

import boto3
import pytest
from botocore.exceptions import ConnectionClosedError, EndpointConnectionError

from apoio import Api, criar_tabelas

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT") or "http://localhost:8000"


@pytest.fixture(scope="session")
def dynamodb():
    cliente = boto3.client(
        "dynamodb",
        endpoint_url=ENDPOINT,
        region_name="sa-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
    for _ in range(15):
        try:
            cliente.list_tables()
            return cliente
        except (EndpointConnectionError, ConnectionClosedError):
            time.sleep(1)
    if os.environ.get("CI"):
        pytest.fail(f"DynamoDB Local não respondeu em {ENDPOINT}")
    pytest.skip(f"DynamoDB Local não está rodando em {ENDPOINT}")


@pytest.fixture
def api(dynamodb, monkeypatch):
    nomes = criar_tabelas(dynamodb, sufixo=f"-{uuid.uuid4().hex[:8]}")
    monkeypatch.setenv("DYNAMODB_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "sa-east-1")
    monkeypatch.delenv("EXIGIR_TOKEN", raising=False)
    monkeypatch.delenv("REMETENTE", raising=False)
    for variavel, nome in nomes.items():
        monkeypatch.setenv(variavel, nome)
    yield Api()
    for nome in nomes.values():
        dynamodb.delete_table(TableName=nome)
