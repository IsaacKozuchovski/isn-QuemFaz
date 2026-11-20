import importlib.util
import json
import sys
import uuid
from pathlib import Path


FUNCOES = Path(__file__).resolve().parent.parent / "functions"

TABELAS = {"MEMBROS_TABLE": "Membros", "NUCLEOS_TABLE": "Nucleos", "TAREFAS_TABLE": "Tarefas"}


def criar_tabelas(dynamodb, sufixo=""):
    nomes = {var: nome + sufixo for var, nome in TABELAS.items()}
    dynamodb.create_table(
        TableName=nomes["MEMBROS_TABLE"],
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "membroId", "AttributeType": "S"},
            {"AttributeName": "nucleoId", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "membroId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "nucleoId-index",
                "KeySchema": [{"AttributeName": "nucleoId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    dynamodb.create_table(
        TableName=nomes["NUCLEOS_TABLE"],
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "nucleoId", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "nucleoId", "KeyType": "HASH"}],
    )
    dynamodb.create_table(
        TableName=nomes["TAREFAS_TABLE"],
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "nucleoId", "AttributeType": "S"},
            {"AttributeName": "tarefaId", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "nucleoId", "KeyType": "HASH"},
            {"AttributeName": "tarefaId", "KeyType": "RANGE"},
        ],
    )
    return nomes


class Api:
    def __init__(self):
        sys.modules.pop("comum", None)
        self._handlers = {}

    def handler(self, pasta):
        if pasta not in self._handlers:
            spec = importlib.util.spec_from_file_location(
                f"handler_{pasta}_{uuid.uuid4().hex}", FUNCOES / pasta / "handler.py"
            )
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            self._handlers[pasta] = modulo
        return self._handlers[pasta]

    def chamar(self, pasta, metodo, rota, membro=None, corpo=None, path=None, query=None):
        evento = {
            "httpMethod": metodo,
            "resource": rota,
            "headers": {"x-membro-id": membro} if membro else {},
            "body": json.dumps(corpo) if corpo is not None else None,
            "pathParameters": path,
            "queryStringParameters": query,
        }
        r = self.handler(pasta).handler(evento, None)
        return r["statusCode"], json.loads(r["body"])

    def login(self, membro, nome=None, idade=None):
        corpo = {} if nome is None else {"nome": nome, "idade": idade, "email": f"{membro}@teste"}
        return self.chamar("login", "POST", "/login", membro, corpo)

    def criar_nucleo(self, membro, nome="Família Teste"):
        return self.chamar("nucleos", "POST", "/nucleos", membro, {"nome": nome})

    def entrar_nucleo(self, membro, nucleo_id):
        return self.chamar(
            "nucleos", "POST", "/nucleos/{nucleoId}/membros", membro, path={"nucleoId": nucleo_id}
        )

    def consultar_nucleo(self, membro, nucleo_id):
        return self.chamar(
            "nucleos", "GET", "/nucleos/{nucleoId}", membro, path={"nucleoId": nucleo_id}
        )

    def criar_tarefa(self, membro, **campos):
        tarefa = {"nome": "Lavar a louça", "pontos": 10, "horarioLimite": "2099-01-01T18:00:00Z"}
        tarefa.update(campos)
        return self.chamar("tarefas", "POST", "/tarefas", membro, tarefa)

    def listar_tarefas(self, membro, status=None):
        query = {"status": status} if status else None
        return self.chamar("tarefas", "GET", "/tarefas", membro, query=query)

    def escolher(self, membro, tarefa_id):
        return self.chamar(
            "tarefas", "POST", "/tarefas/{tarefaId}/escolher", membro, path={"tarefaId": tarefa_id}
        )

    def concluir(self, membro, tarefa_id):
        return self.chamar(
            "tarefas", "POST", "/tarefas/{tarefaId}/concluir", membro, path={"tarefaId": tarefa_id}
        )

    def aprovar(self, membro, tarefa_id, aprovado=True):
        return self.chamar(
            "aprovar", "POST", "/aprovar", membro, {"tarefaId": tarefa_id, "aprovado": aprovado}
        )

    def placar(self, membro):
        return self.chamar("placar", "GET", "/placar", membro)

    def sortear(self):
        return self.handler("sortear").handler({}, None)

    @property
    def tabelas(self):
        import comum

        return comum
