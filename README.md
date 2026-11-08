# Karaokê com IA

Sistema inteligente de karaokê desenvolvido em Python, projetado com foco em Clean Architecture, separação de faixas por inteligência artificial e avaliação objetiva da performance vocal (pontuação de 0 a 100).

---

## Principais Funcionalidades

- **Fonte Híbrida de Músicas**: Pesquisa e download direto do YouTube (via `yt-dlp`) ou upload de arquivos de áudio locais (`.mp3`, `.wav`).
- **Isolamento Vocal com IA**: Separação automática entre faixa instrumental (playback) e voz de referência utilizando Demucs (suporte a aceleração GPU CUDA ou execução em CPU).
- **Letras Sincronizadas**: Obtenção de letras no formato `.lrc` (via LRCLIB) com destaque em tempo real no estilo karaokê tradicional.
- **Avaliador de Canto com IA (0 a 100)**:
  - **Afinação (Pitch)**: Extração da frequência fundamental ($F_0$) com tolerância a oitavas e semitons.
  - **Ritmo e Tempo (Timing)**: Alinhamento temporal elástico via Dynamic Time Warping (DTW) comparado à faixa original de voz.
- **Interface Web Integrada**: Backend em FastAPI acompanhado de interface web responsiva com gravação de áudio direto pelo navegador (MediaRecorder API).

---

## Arquitetura

O projeto adota rigorosamente a Clean Architecture, garantindo que as regras de negócio centrais permaneçam totalmente desacopladas de frameworks web, bibliotecas de inteligência artificial ou detalhes de infraestrutura e persistência.

Para entender a divisão de responsabilidades e as regras das camadas, consulte os documentos:
- [ARCHITECTURE.md](file:///media/nickzs/D/projetos/karaoke/ARCHITECTURE.md): Detalhamento das camadas, portas, adaptadores e diretórios previstos.
- [AGENTS.md](file:///media/nickzs/D/projetos/karaoke/AGENTS.md): Diretrizes de desenvolvimento, restrições e regras para agentes autônomos.

---

## Pré-requisitos

- **Python 3.11+**
- **FFmpeg** instalado no sistema operacional (necessário para processamento e conversão de áudio):
  ```bash
  # Ubuntu / Debian
  sudo apt update && sudo apt install -y ffmpeg
  ```
- (Opcional): GPU com suporte a CUDA para aceleração do processamento de áudio com Demucs.

---

## Instalação e Execução

### 1. Clonar o repositório
```bash
git clone https://github.com/Nickzs8/karaoke.git
cd karaoke
```

### 2. Criar e ativar o ambiente virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Iniciar o servidor
```bash
uvicorn src.karaoke.infrastructure.main:app --reload --host 0.0.0.0 --port 8000
```
Acesse a aplicação no navegador em `http://localhost:8000`.

---

## Execução de Testes

Para executar a suíte de testes automatizados:

```bash
pytest tests/
```

---

## Licença

Distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais informações.
