VENV ?= .venv
BIN := $(shell if [ -d "$(VENV)/bin" ]; then echo "$(VENV)/bin/"; fi)

.PHONY: help setup env dirs install lint format check test test-unit run run-prod clean clean-storage clean-all docker-build docker-up docker-down docker-logs docker-run docker-restart docker-clean

help: ## Exibe esta lista de comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: install env dirs ## Configuração inicial completa do ambiente local
	@echo "Ambiente configurado com sucesso!"

env: ## Cria o arquivo .env a partir do .env_example caso não exista
	@if [ ! -f .env ]; then \
		cp .env_example .env; \
		echo "Arquivo .env criado a partir de .env_example"; \
	else \
		echo "Arquivo .env já existe."; \
	fi

dirs: ## Garante a existência da estrutura de pastas de storage
	@mkdir -p storage/raw storage/processed storage/recordings storage/lyrics
	@touch storage/raw/.gitkeep storage/processed/.gitkeep storage/recordings/.gitkeep storage/lyrics/.gitkeep

install: ## Instala as dependências Python de produção e desenvolvimento
	$(BIN)pip install --upgrade pip
	$(BIN)pip install -r requirements.txt
	$(BIN)pip install ruff

lint: ## Executa o linter (Ruff) para identificar erros e violações de código
	$(BIN)ruff check src/ tests/

format: ## Formata o código e organiza imports automaticamente com o Ruff
	$(BIN)ruff format src/ tests/
	$(BIN)ruff check --fix src/ tests/

check: lint ## Valida formatação, linter e testes em uma única etapa
	$(BIN)ruff format --check src/ tests/
	PYTHONPATH=src $(BIN)pytest -q

test: ## Executa a suíte de testes automatizados com Pytest
	PYTHONPATH=src $(BIN)pytest

test-unit: ## Executa testes unitários detalhados com saída verbosa
	PYTHONPATH=src $(BIN)pytest tests/unit/ -v

run: ## Inicia o servidor local FastAPI com recarregamento automático (Dev)
	PYTHONPATH=src $(BIN)uvicorn karaoke.presentation.api.app:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Inicia o servidor FastAPI em modo de produção (sem reload)
	PYTHONPATH=src $(BIN)uvicorn karaoke.presentation.api.app:app --host 0.0.0.0 --port 8000

docker-build: ## Constrói a imagem Docker da aplicação com FFmpeg e dependências
	docker compose build

docker-up: ## Inicia o container da API em segundo plano na porta 8000
	docker compose up -d

docker-down: ## Para e remove os containers e redes da aplicação
	docker compose down

docker-logs: ## Acompanha os logs em tempo real do container da API
	docker compose logs -f api

docker-run: ## Inicia o container em primeiro plano exibindo os logs ao vivo
	docker compose up

docker-restart: ## Reinicia os containers Docker da aplicação
	docker compose restart

docker-clean: ## Para os containers e remove volumes e imagens antigas
	docker compose down -v --rmi local

clean: ## Remove arquivos temporários de cache e compilação do Python
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

clean-storage: ## Remove arquivos de áudio temporários preservando a estrutura
	find storage/raw/ -type f ! -name ".gitkeep" -delete
	find storage/recordings/ -type f ! -name ".gitkeep" -delete
	find storage/processed/ -type f ! -name ".gitkeep" -delete
	find storage/lyrics/ -type f ! -name ".gitkeep" -delete
	@echo "Mídias locais do storage removidas com segurança."

clean-all: clean clean-storage ## Limpa todos os caches e arquivos de mídia temporários
