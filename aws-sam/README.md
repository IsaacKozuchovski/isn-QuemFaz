# Backend QuemFaz (AWS SAM)

API Gateway + Lambda (Python/boto3) + DynamoDB, definido no [template.yaml](template.yaml). Cada função fica em `functions/<nome>/handler.py`; o código compartilhado fica no layer `functions/comum/`.

## Banco de dados (DynamoDB)

| Tabela | Chave | Atributos |
|---|---|---|
| `Membros` | `membroId` | nome, email, idade, nucleoId, pontos · índice `nucleoId-index` |
| `Nucleos` | `nucleoId` | nome, criadoPor |
| `Tarefas` | `nucleoId` + `tarefaId` | nome, pontos, idadeMinima, horarioLimite, status, responsavel |

Localmente o banco roda no DynamoDB Local (Docker); na AWS, as tabelas são criadas pelo template.

## API

O usuário é identificado pelo header `x-membro-id` (será substituído pelo Cognito).

| Método | Rota | Descrição |
|---|---|---|
| POST | `/login` | Cria ou retorna o membro |
| POST | `/nucleos` | Cria um núcleo familiar |
| POST | `/nucleos/{nucleoId}/membros` | Entra num núcleo |
| GET / POST | `/tarefas` | Lista / cadastra tarefas |
| POST | `/tarefas/{tarefaId}/escolher` | Assume uma tarefa |
| POST | `/tarefas/{tarefaId}/concluir` | Marca como concluída |
| POST | `/aprovar` | Aprova ou rejeita a conclusão |
| GET | `/placar` | Pontuação do núcleo |

## Como rodar

```bash
make dev    # sobe DynamoDB Local + API local (porta 3000) no tmux
make demo   # testa o fluxo completo
make stop   # derruba tudo
```
