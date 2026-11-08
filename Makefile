.PHONY: help install lint format test run clean

help: ## Exibe esta lista de comandos disponíveis
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

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
	pytest

run: ## Inicia o servidor local FastAPI com recarregamento automático
	uvicorn src.karaoke.infrastructure.main:app --reload --host 0.0.0.0 --port 8000

clean: ## Remove arquivos temporários de cache e compilação do Python
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
