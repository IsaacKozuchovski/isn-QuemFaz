# Backend QuemFaz (AWS SAM)

API Gateway + Lambda (Python/boto3) + DynamoDB, definido no [template.yaml](template.yaml). Cada função fica em `functions/<nome>/handler.py`; o código compartilhado fica no layer `functions/comum/`.

## Banco de dados (DynamoDB)

| Tabela | Chave | Atributos |
|---|---|---|
| `Membros` | `membroId` | nome, email, idade, nucleoId, pontos · índice `nucleoId-index` |
| `Nucleos` | `nucleoId` | nome, criadoPor |
| `Tarefas` | `nucleoId` + `tarefaId` | nome, descricao (opcional), pontos, idadeMinima, horarioLimite, status, criadaPor, responsavel, aprovadaPor, sorteada |

Localmente o banco roda no DynamoDB Local (Docker); na AWS, as tabelas são criadas pelo Pulumi.

## API

Na AWS, o usuário é identificado pelo token do login com Google (Cognito), e o API Gateway recusa quem não tem token válido.

Localmente (`make dev`) e nos testes automáticos não existe Cognito, então o usuário é identificado pelo header `x-membro-id`. Na AWS, esse header é ignorado.

| Método | Rota | Descrição |
|---|---|---|
| POST | `/login` | Cria ou retorna o membro |
| POST | `/nucleos` | Cria um núcleo familiar |
| POST | `/nucleos/{nucleoId}/membros` | Entra num núcleo |
| GET | `/nucleos/{nucleoId}` | Dados do núcleo (nome) |
| GET / POST | `/tarefas` | Lista / cadastra tarefas |
| POST | `/tarefas/{tarefaId}/escolher` | Assume uma tarefa |
| POST | `/tarefas/{tarefaId}/concluir` | Marca como concluída |
| POST | `/aprovar` | Aprova ou rejeita a conclusão |
| GET | `/placar` | Pontuação do núcleo |

Além das rotas, a função `sortear` roda a cada 5 minutos (EventBridge Scheduler): sorteia as tarefas vencidas que ninguém escolheu e avisa o sorteado por email (UC06).
