# Imagem base leve com Python 3.12
FROM python:3.12-slim

# Evita que o Python gere arquivos .pyc e força logs stdout imediatos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    KARAOKE_STORAGE_DIR=/app/storage

WORKDIR /app

# Instala dependências de sistema essenciais para processamento de áudio (FFmpeg e libsndfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Cria a estrutura de pastas para persistência local de áudios
RUN mkdir -p /app/storage/raw /app/storage/processed /app/storage/recordings /app/storage/lyrics

# Copia o código-fonte da aplicação
COPY src/ /app/src/
COPY pyproject.toml .

# Porta padrão de exposição da API
EXPOSE 8000

# Inicializa o servidor FastAPI com Uvicorn
CMD ["uvicorn", "karaoke.presentation.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
