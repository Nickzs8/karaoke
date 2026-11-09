.PHONY: help install lint format test run clean docker-build docker-up docker-down docker-logs docker-run

help: ## Exibe esta lista de comandos disponíveis
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências de produção e desenvolvimento
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install ruff

lint: ## Executa o linter (Ruff) para identificar erros e violações de padrão
	ruff check .

format: ## Formata o código e ordena imports automaticamente (Ruff)
	ruff format .
	ruff check --fix .

test: ## Executa a suíte de testes automatizados com Pytest
	PYTHONPATH=src pytest

run: ## Inicia o servidor local FastAPI com recarregamento automático
	PYTHONPATH=src uvicorn karaoke.presentation.api.app:app --reload --host 0.0.0.0 --port 8000

docker-build: ## Constrói a imagem Docker da aplicação com FFmpeg e dependências
	docker compose build

docker-up: ## Inicia o container da API em segundo plano (porta 8000)
	docker compose up -d

docker-down: ## Para e remove os containers e redes da aplicação
	docker compose down

docker-logs: ## Acompanha os logs em tempo real do container da API
	docker compose logs -f api

docker-run: ## Inicia o container em primeiro plano exibindo os logs
	docker compose up

clean: ## Remove arquivos temporários de cache e compilação do Python
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
