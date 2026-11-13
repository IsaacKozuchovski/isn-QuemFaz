NODE_VERSION := 22.19.0
# linux-x64, darwin-arm64, darwin-x64...
NODE_OS      := $(shell uname -s | tr A-Z a-z)
NODE_ARCH    := $(shell uname -m | sed 's/x86_64/x64/; s/aarch64/arm64/')
NODE_DIST    := node-v$(NODE_VERSION)-$(NODE_OS)-$(NODE_ARCH)

# As ferramentas instaladas por `make install` ficam em ~/.local/bin e ~/.pulumi/bin.
# Vão no FIM do PATH: se o sistema já tem a ferramenta, a do sistema vale.
export PATH := $(PATH):$(HOME)/.local/bin:$(HOME)/.pulumi/bin

STACK ?= dev
SISTEMA := $(shell uname -s)

.PHONY: all install aws_cli aws_sam_cli pulumi uv node shell \
        deploy check dev backend frontend stop

## ---- Uso -------------------------------------------------------------------
#   make          instala o que faltar (Pulumi, uv, Node.js, AWS CLI, SAM)
#   make deploy   pulumi up no stack dev (cria o stack se não existir)
all: install

# $(call garantir,<comando>,<alvo no Linux>,<pacote no Homebrew>)
# Se o comando já funciona, não faz nada; senão instala do jeito do sistema.
# (testa com --version, e não só se existe: um binário de Linux copiado para
# um Mac existe, mas não executa)
ifeq ($(SISTEMA),Darwin)
garantir = $(1) --version > /dev/null 2>&1 && echo "✓ $(1)" || brew install $(3)
else
garantir = $(1) --version > /dev/null 2>&1 && echo "✓ $(1)" || $(MAKE) $(2)
endif

install:
ifeq ($(SISTEMA),Darwin)
	@command -v brew > /dev/null || { echo "✗ Instale o Homebrew antes: https://brew.sh"; exit 1; }
endif
	@$(call garantir,pulumi,pulumi,pulumi/tap/pulumi)
	@$(call garantir,uv,uv,uv)
	@$(call garantir,npm,node,node)
	@$(call garantir,aws,aws_cli,awscli)
	@$(call garantir,sam,aws_sam_cli,aws-sam-cli)
ifneq ($(SISTEMA),Darwin)
	@$(MAKE) --no-print-directory shell
endif
	@echo
	@echo "✓ Tudo pronto. Próximo passo: make deploy"

aws_cli:
	curl -sL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
	unzip awscliv2.zip

	rm -rf ~/.aws-cli
	./aws/install -i ~/.aws-cli -b ~/.local/bin

	rm -f awscliv2.zip
	rm -rf aws

aws_sam_cli:
	curl -sL https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip -o aws-sam-cli-linux-x86_64.zip
	unzip aws-sam-cli-linux-x86_64.zip -d sam-installation

	rm -rf ~/.aws-sam-cli
	./sam-installation/install -i ~/.aws-sam-cli -b ~/.local/bin

	rm -f aws-sam-cli-linux-x86_64.zip
	rm -rf sam-installation

pulumi:
	curl -fsSL https://get.pulumi.com | sh

uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js (para o build do frontend), instalado em ~/.local sem precisar de sudo
node:
	curl -fsSL https://nodejs.org/dist/v$(NODE_VERSION)/$(NODE_DIST).tar.gz | tar -xz -C /tmp
	rm -rf ~/.local/node
	mkdir -p ~/.local/bin
	mv /tmp/$(NODE_DIST) ~/.local/node
	ln -sf ~/.local/node/bin/node ~/.local/node/bin/npm ~/.local/node/bin/npx ~/.local/bin/

# Acrescenta ao ~/.bashrc (sem apagar o que já existe e sem repetir)
shell:
	@grep -qF '# QuemFaz' ~/.bashrc 2>/dev/null || { \
		echo '# QuemFaz'; \
		echo 'export PATH="$$HOME/.local/bin:$$HOME/.pulumi/bin:$$PATH"'; \
		echo 'complete -C "$$HOME/.local/bin/aws_completer" aws'; \
	} >> ~/.bashrc

## ---- Deploy: `make deploy` (ou STACK=prod make deploy) -------------------
# Confere login e credenciais antes; o programa Pulumi faz o build do frontend.
deploy:
	@pulumi version > /dev/null 2>&1 || { echo "✗ Pulumi não encontrado: rode 'make' antes"; exit 1; }
	@pulumi whoami > /dev/null 2>&1 || pulumi login
	@aws sts get-caller-identity > /dev/null 2>&1 || { \
		echo "✗ Sem credenciais da AWS: rode 'aws configure' com a Access Key do usuário IAM"; exit 1; }
	cd pulumi && pulumi stack select $(STACK) --create && pulumi up

## ---- Rodar o sistema localmente ------------------------------------------
# `make dev`: sobe banco + API + frontend no mesmo terminal (Ctrl+C para tudo).
# Depois, `make stop` derruba o DynamoDB Local.

check:
	@command -v docker > /dev/null || { echo "✗ Docker não encontrado: instale o Docker"; exit 1; }
	@docker info > /dev/null 2>&1  || { echo "✗ O Docker está instalado, mas não está rodando: abra o Docker"; exit 1; }
	@sam --version > /dev/null 2>&1 || { echo "✗ AWS SAM CLI não encontrado: rode 'make'"; exit 1; }
	@npm --version > /dev/null 2>&1 || { echo "✗ Node.js não encontrado: rode 'make'"; exit 1; }
	@echo "✓ Docker, SAM e Node.js ok"

dev: check
	$(MAKE) -C aws-sam up
	@echo
	@echo ">>> Frontend em http://localhost:5173 (a API sobe em ~1 min; Ctrl+C para parar)"
	@echo
	$(MAKE) -j2 backend frontend

backend:
	$(MAKE) -C aws-sam api

frontend:
	cd frontend && npm ci --no-audit --no-fund && npm run dev

stop:
	$(MAKE) -C aws-sam stop
