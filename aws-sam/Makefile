SESSION  := sam-dev
NETWORK  := sam-local
ENDPOINT := http://localhost:8000
API      := http://127.0.0.1:3000
MEMBRO   ?= membro-1
NOME     ?= Ada Lovelace
IDADE    ?= 30
NUCLEO   ?=
TAREFA   ?=
APROVADO ?= true
TABLE    ?= Tarefas

# Dummy credentials, exported to every command below (used by the aws CLI)
export AWS_ACCESS_KEY_ID     := local
export AWS_SECRET_ACCESS_KEY := local
export AWS_DEFAULT_REGION    := sa-east-1

.PHONY: dev up logs wait-table build api login nucleo entrar tarefa tarefas escolher concluir aprovar placar demo scan stop clean

## ---- tmux layout ---------------------------------------------------------
dev:
	@if tmux has-session -t $(SESSION) 2>/dev/null; then \
		exec tmux attach -t $(SESSION); \
	fi; \
	tmux new-session -d -s $(SESSION) -c "$(CURDIR)"; \
	TOP=$$(tmux display-message -p -t $(SESSION) '#{pane_id}'); \
	RIGHT=$$(tmux split-window -h -t $$TOP -c "$(CURDIR)" -P -F '#{pane_id}'); \
	BOTTOM=$$(tmux split-window -v -t $$TOP -c "$(CURDIR)" -P -F '#{pane_id}'); \
	tmux send-keys -t $$TOP    "make up logs" C-m; \
	tmux send-keys -t $$BOTTOM "make api" C-m; \
	tmux send-keys -t $$RIGHT  "clear" C-m; \
	tmux send-keys -t $$RIGHT  "make demo"; \
	tmux select-pane -t $$RIGHT; \
	exec tmux attach -t $(SESSION)

## ---- top left: Docker ----------------------------------------------------
up:
	docker compose down
	docker compose up -d

logs:
	docker compose logs -f

## ---- bottom left: SAM ----------------------------------------------------
wait-table:
	@echo "Waiting for the table to be created..."
	@until docker compose logs create-table 2>/dev/null | grep -q 'TABLE CREATED'; do sleep 1; done

build:
	sam build

api: wait-table build
	sam local start-api --env-vars env.json --docker-network $(NETWORK)

## ---- right: client -------------------------------------------------------
# Use MEMBRO=<id> para simular usuários diferentes (enquanto o Cognito não está ligado)
CURL = curl -s -H 'Content-Type: application/json' -H 'x-membro-id: $(MEMBRO)'

login:
	$(CURL) -X POST $(API)/login -d '{"nome": "$(NOME)", "idade": $(IDADE)}'; echo

nucleo:
	$(CURL) -X POST $(API)/nucleos -d '{"nome": "Família $(NOME)"}'; echo

entrar:
	$(CURL) -X POST $(API)/nucleos/$(NUCLEO)/membros; echo

tarefa:
	$(CURL) -X POST $(API)/tarefas \
		-d '{"nome": "Lavar a louça", "pontos": 10, "idadeMinima": 10, "horarioLimite": "2099-01-01T18:00:00Z"}'; echo

tarefas:
	$(CURL) $(API)/tarefas; echo

escolher:
	$(CURL) -X POST $(API)/tarefas/$(TAREFA)/escolher; echo

concluir:
	$(CURL) -X POST $(API)/tarefas/$(TAREFA)/concluir; echo

aprovar:
	$(CURL) -X POST $(API)/aprovar -d '{"tarefaId": "$(TAREFA)", "aprovado": $(APROVADO)}'; echo

placar:
	$(CURL) $(API)/placar; echo

# Fluxo completo com dois membros (criar núcleo → tarefa → escolher → concluir → aprovar → placar)
demo:
	./demo.sh $(API)

scan:
	aws dynamodb scan --table-name $(TABLE) --endpoint-url $(ENDPOINT)

## ---- teardown -------------------------------------------------------------
stop:
	docker compose down
	-tmux kill-session -t $(SESSION)

clean: stop
	rm -rf .aws-sam