# 🏛️ Guia de Arquitetura: Clean Architecture

Este documento descreve as decisões arquiteturais adotadas no projeto **Karaokê com IA**. O objetivo principal é manter as regras de negócio puras, testáveis e completamente isoladas de detalhes externos (como frameworks web, modelos de aprendizado de máquina, bibliotecas de DSP e sistemas de arquivos).

---

## 1. Princípios Fundamentais

A estrutura deste projeto é baseada na **Clean Architecture** (Arquitetura Limpa) de Robert C. Martin (Uncle Bob), fundamentada nas seguintes diretrizes:

1. **A Regra da Dependência**: O código das camadas internas nunca pode importar, conhecer ou depender de nada que esteja em uma camada externa. Todas as setas de dependência apontam para dentro:
   $$\text{Frameworks \& Drivers} \longrightarrow \text{Adapters} \longrightarrow \text{Application (Casos de Uso)} \longrightarrow \text{Domain (Entidades)}$$
2. **Inversão de Dependência via Portas (Interfaces)**: Quando um caso de uso precisa de um recurso externo (ex: baixar áudio ou extrair afinação), ele define uma **Porta (Protocol/Interface)** na camada de aplicação. A camada de adaptadores implementa essa porta.
3. **Independência de Frameworks**: O domínio e os casos de uso não sabem que o FastAPI, PyTorch, Librosa ou Demucs existem. Se amanhã decidirmos trocar o FastAPI pelo Flask, ou o Demucs por outro modelo de separação, o núcleo do negócio não sofre alteração alguma.
4. **Testabilidade Isolada**: Casos de uso e entidades podem ser testados de forma unitária em milissegundos, utilizando mocks ou implementações em memória das portas.

---

## 2. Visão dos Diretórios Previstos

Abaixo está o mapa dos diretórios do projeto e a responsabilidade exclusiva de cada um:

```
karaoke/
├── storage/                    # Armazenamento físico de áudio e arquivos locais
├── src/
│   └── karaoke/
│       ├── domain/             # CAMADA 1: Entidades e Objetos de Valor
│       ├── application/        # CAMADA 2: Casos de Uso e Portas (Interfaces)
│       │   ├── ports/          # Contratos abstratos (Protocols)
│       │   └── use_cases/      # Orquestradores do fluxo de negócio
│       ├── adapters/           # CAMADA 3: Implementações das Portas e Adaptadores
│       │   ├── downloaders/    # Adaptadores de download de áudio
│       │   ├── separators/     # Adaptadores de separação vocal/instrumental
│       │   ├── lyrics/         # Adaptadores de busca de letras sincronizadas
│       │   ├── audio/          # Adaptadores de análise acústica e pontuação
│       │   └── storage/        # Adaptadores de persistência em disco
│       ├── infrastructure/     # CAMADA 4: Configurações e Injeção de Dependências
│       └── presentation/       # CAMADA 4: Web API e Interface Gráfica
│           ├── api/            # Rotas, schemas e controladores HTTP
│           └── web/            # Arquivos estáticos (HTML/CSS/JS) do frontend
└── tests/                      # Bateria de testes automatizados
    ├── unit/                   # Testes unitários de domínio e casos de uso
    └── integration/            # Testes de integração dos adaptadores
```

---

## 3. Detalhamento de Cada Diretório

### 🟢 Camada 1: Domínio (`src/karaoke/domain/`)
* **Responsabilidade**: Contém as regras de negócio corporativas, entidades e objetos de valor.
* **Regra**: **Zero dependências externas**. Utiliza apenas tipos primitivos do Python e bibliotecas padrão (`dataclasses`, `typing`, `enum`).
* **Conteúdo**:
  * Representação de conceitos como `Song` (música), `Performance` (sessão de canto do usuário) e `ScoreResult` (resultado da nota final).
  * Objetos de valor como curvas de frequência fundamental ($F_0$), intervalos de notas musicais e validações de pontuação (0 a 100).

---

### 🟡 Camada 2: Aplicação (`src/karaoke/application/`)
* **Responsabilidade**: Contém as regras de negócio da aplicação. Orquestra o fluxo de dados entre as entidades e as portas externas.
* **Subdiretórios**:
  * `ports/`: Define as interfaces abstratas (usando `typing.Protocol` ou `abc.ABC`) que o sistema necessita para operar.
    * *Exemplos de portas*: contrato para baixar faixas, contrato para isolar faixas de voz/instrumental, contrato para buscar letras sincronizadas, contrato para calcular curvas de frequência e contrato para persistir dados.
  * `use_cases/`: Contém as classes que executam fluxos específicos de ponta a ponta.
    * *Exemplos de casos de uso*: preparar uma música (baixar + separar faixas + sincronizar letra), avaliar a performance vocal do usuário e listar catálogo disponível.

---

### 🟠 Camada 3: Adaptadores de Interface (`src/karaoke/adapters/`)
* **Responsabilidade**: Traduz os dados do formato mais conveniente para as entidades/casos de uso para o formato exigido por bibliotecas ou serviços externos.
* **Subdiretórios**:
  * `downloaders/`: Implementa as portas de download utilizando ferramentas externas (ex: `yt-dlp`).
  * `separators/`: Implementa o isolamento de voz e instrumental acoplando a biblioteca de IA escolhida (ex: `demucs`).
  * `lyrics/`: Implementa a busca e parsing de letras sincronizadas em formato `.lrc` (ex: cliente para LRCLIB).
  * `audio/`: Implementa os algoritmos de análise de sinal (DSP), detecção de pitch (ex: `librosa`, `crepe`) e alinhamento rítmico via Dynamic Time Warping (DTW).
  * `storage/`: Implementa a persistência e localização dos arquivos de mídia salvos no disco local.

---

### 🔴 Camada 4: Infraestrutura e Apresentação

#### `src/karaoke/infrastructure/`
* **Responsabilidade**: Configurações globais e inicialização do sistema.
* **Conteúdo**:
  * Leitura de variáveis de ambiente (detecção de GPU/CUDA ou CPU, diretórios de trabalho).
  * **Composition Root (Container)**: Ponto único onde as dependências são instanciadas e injetadas nos casos de uso.

#### `src/karaoke/presentation/`
* **Responsabilidade**: Interface de entrada de dados e interação com o usuário final.
* **Subdiretórios**:
  * `api/`: Servidor web (FastAPI), definição de rotas REST, serialização de requisições e respostas (schemas Pydantic).
  * `web/`: Recursos de frontend (páginas HTML, folhas de estilo CSS, scripts JavaScript para captura de microfone via `MediaRecorder` e player de áudio).

---

### 📦 Diretórios de Suporte

* `storage/`: Diretório local dedicado a armazenar arquivos de mídia gerados em tempo de execução (áudios brutos baixados, faixas separadas, gravações do usuário e arquivos de letras). **Deve ser ignorado pelo Git**.
* `tests/`:
  * `tests/unit/`: Testes rápidos que validam o domínio e os casos de uso utilizando mocks para as portas.
  * `tests/integration/`: Testes que avaliam a integração real dos adaptadores com arquivos de áudio de amostra.

---

## 4. Fluxo Típico de Execução (Exemplo: Avaliação de Canto)

1. **Apresentação**: O usuário canta pelo navegador e envia o áudio gravado para o endpoint da `presentation/api/`.
2. **Caso de Uso**: O controlador HTTP chama o caso de uso `EvaluatePerformanceUseCase` presente em `application/use_cases/`.
3. **Portas & Adaptadores**: O caso de uso aciona:
   * A porta de armazenamento para recuperar a faixa vocal original e a gravação.
   * A porta de áudio (`adapters/audio/`) para extrair as frequências fundamentais ($F_0$) de ambas as faixas.
   * O algoritmo de alinhamento temporal e afinação para calcular a dispersão em semitons e ritmo.
4. **Domínio**: As entidades do `domain/` consolidam a nota final (0 a 100) e os detalhes de desempenho.
5. **Retorno**: O caso de uso devolve o resultado para a camada de apresentação, que responde o JSON formatado para o usuário.
