# 🤖 Diretrizes para Agentes Autônomos (AGENTS.md)

Este documento define as regras, restrições arquiteturais e padrões de desenvolvimento que **todos os agentes de IA** (e desenvolvedores humanos) devem seguir ao criar, modificar ou refatorar código neste repositório.

---

## 1. Guardrails Arquiteturais (Regras Inegociáveis)

O projeto segue estritamente a **Clean Architecture**. A violação dessas regras quebra a integridade do projeto:

1. **Pureza do Domínio (`src/karaoke/domain/`)**:
   - **NÃO** importe nenhuma biblioteca de terceiros nesta camada (proibido: `fastapi`, `pydantic`, `torch`, `demucs`, `librosa`, `yt_dlp`, etc.).
   - Utilize apenas a biblioteca padrão do Python (`dataclasses`, `typing`, `enum`, `math`, `abc`, `pathlib`).
   - Mantenha as entidades e objetos de valor focados em conceitos de negócio e validações puras.

2. **Inversão de Dependência na Aplicação (`src/karaoke/application/`)**:
   - Os casos de uso (`application/use_cases/`) nunca devem instanciar adaptadores concretos diretamente.
   - Qualquer necessidade de I/O, rede, aprendizado de máquina ou persistência deve ser expressa como um contrato em `application/ports/` (utilize `typing.Protocol`).
   - O caso de uso deve receber suas dependências via construtor (`__init__`).

3. **Isolamento de Adaptadores (`src/karaoke/adapters/`)**:
   - Todo código acoplado a bibliotecas externas (ex: `demucs`, `yt-dlp`, `librosa`, `scipy`) deve residir exclusivamente dentro de seu respectivo pacote em `adapters/`.
   - Um adaptador implementa uma porta definida em `application/ports/`.

4. **Raiz de Composição (`src/karaoke/infrastructure/`)**:
   - Apenas o pacote de infraestrutura (ou o container de injeção de dependência) tem permissão para instanciar os adaptadores concretos e conectá-los aos casos de uso.

5. **Exceções de Domínio (Centralização Obrigatória)**:
   - **TODOS os erros e exceções do sistema devem estar definidos em `src/karaoke/domain/exceptions.py`** e herdar de `DomainError`.
   - É **terminantemente proibido lançar exceções genéricas nativas do Python** (ex: `ValueError`, `TypeError`, `RuntimeError`) no domínio ou adaptadores para validações de parâmetros, regras de negócio ou falhas operacionais. Lance sempre uma exceção específica de domínio.
   - Crie exceções customizadas para erros de negócio e validações (ex: `SongNotFoundError`, `InvalidScoreError`, `InvalidPitchPointError`, `InvalidScorerConfigError`, `AudioSeparationError`).
   - Adaptadores devem capturar exceções externas de bibliotecas terceiras e encapsulá-las em exceções de domínio antes de propagá-las.

---

## 2. Padrões de Código e Tipagem

- **Versão do Python**: 3.11+.
- **Princípio da Responsabilidade Única (SRP / SOLID)**:
  - **Proibido criar funções "monolíticas" ou gigantescas** que acumulem múltiplos papéis (ex: validação, configuração, chamadas externas, parsing de dados e manipulação de arquivos na mesma função).
  - Toda operação deve ser decomposta em **pequenas funções coesas e especializadas**, onde cada método faz **uma única coisa bem feita**.
  - Métodos públicos principais devem atuar apenas como **orquestradores de alto nível**, delegando tarefas específicas para métodos privados bem nomeados e tipados.
- **Tipagem Estrita**: Todas as funções, métodos e atributos de classe devem conter anotações de tipo (`type hints`).
- **Data Transfer Objects (DTOs)**:
  - Para a camada web/API: use **Pydantic V2** em `presentation/api/schemas.py`.
  - Para o domínio interno: use `@dataclass(frozen=True)` para Value Objects e `@dataclass` para Entidades.
- **Assincronismo**:
  - Operações de I/O de rede ou processamento rápido podem ser assíncronas (`async/await`).
  - Tarefas de áudio pesadas (Demucs, Librosa) devem ser despachadas para threads ou process pools apropriados para evitar bloqueio do event loop do FastAPI.

---

## 3. Gestão de Mídias e Hardware

- **Diretório `storage/`**:
  - Todos os arquivos temporários de áudio (downloads, faixas separadas, gravações) devem ser salvos dentro de subpastas do diretório `storage/`.
  - **Nunca adicione arquivos de áudio ao controle de versão (Git)**.
- **Suporte Híbrido de Hardware**:
  - Sempre verifique a disponibilidade de CUDA (`torch.cuda.is_available()`).
  - Forneça fallback gracioso para CPU com parâmetros mais leves caso uma GPU dedicada não esteja presente.

---

## 4. Estratégia de Testes

Ao implementar novas funcionalidades, siga esta estratégia de testes:

- **Testes Unitários (`tests/unit/`)**:
  - Teste as entidades e regras do `domain/`.
  - Teste os casos de uso em `application/use_cases/` utilizando implementações de teste (Mocks/Fakes) das interfaces de `application/ports/`.
  - Testes unitários devem rodar de forma rápida sem depender de internet, microfone ou GPU.
- **Testes de Integração (`tests/integration/`)**:
  - Teste adaptadores individuais isoladamente com arquivos de áudio sintéticos ou de amostra mínima.

---

## 5. Tomada de Decisão e Gestão de Incertezas

- **Nunca assuma sozinho**: Se houver qualquer dúvida, ambiguidade de requisitos ou incerteza técnica sobre qual direção seguir, **NÃO tome decisões arbitrárias por conta própria**.
- **Sempre pergunte ao usuário**: Pare e pergunte diretamente ao usuário, expondo as opções e trade-offs para que ele defina o caminho desejado antes de implementar.

---

## 6. Agente Avaliador de Código (Code Reviewer Agent)

Sempre que um agente de IA editar, refatorar ou criar código neste repositório, o **Agente Avaliador de Código** deve ser acionado para auditar as mudanças antes que a tarefa seja dada como concluída.

### 6.1. Critérios de Avaliação Obrigatórios
O avaliador revisa a solução com base em 4 pilares:

1. **Funcionamento e Verificação Real**:
   - O código funciona de verdade? A suíte de testes (`pytest`) roda e passa integralmente sem regressões?
   - Os novos fluxos possuem testes unitários condizentes?

2. **Conformidade Arquitetural (Clean Architecture)**:
   - A pureza do domínio foi violada? (Nenhuma lib externa em `domain/`).
   - Há acoplamento indevido ou funções monolíticas violando o SRP?
   - Todos os erros usam subclasses de `DomainError` de `domain/exceptions.py` (sem `ValueError` ou exceções genéricas)?

3. **Princípio do Menor Esforço e Minimalismo (KISS / Minimal Diff)**:
   - A alteração fez o **mínimo de mudanças possíveis** para atingir o objetivo?
   - O código **reutilizou métodos, portas e classes já existentes** em vez de reinventar a roda ou duplicar lógica?
   - Evitou *over-engineering*, abstrações desnecessárias ou modificações em arquivos não relacionados?

4. **Qualidade Lógica e Tipagem**:
   - A lógica é clara, direta e robusta a falhas?
   - Todas as funções e retornos possuem *type hints* estritos?

### 6.2. Emissão do Veredito ao Agente Principal
O avaliador deve analisar o `git diff` e o resultado dos testes, enviando seu veredito formal ao agente principal:
- **`[VEREDITO: APROVADO]`**: Código funcional, enxuto, aderente à arquitetura e com o menor esforço necessário.
- **`[VEREDITO: REPROVADO]`**: Lista objetiva dos problemas encontrados (ex: excesso de código, violação arquitetural, quebra de teste, falta de reaproveitamento), instruindo o agente principal a corrigir antes de finalizar.

---

## 7. Checklist para Agentes antes de Concluir Tarefas

- [ ] As novas classes respeitam o limite de sua camada?
- [ ] Nenhuma biblioteca externa foi importada dentro de `domain/` ou `application/`?
- [ ] As funções seguem o princípio de responsabilidade única (SRP), sem métodos gigantes monolíticos?
- [ ] Foram adicionados tipos estáticos em todos os argumentos e retornos?
- [ ] Em caso de incerteza ou ambiguidade, o usuário foi consultado antes de assumir decisões?
- [ ] Todos os erros lançados estão definidos em `domain/exceptions.py` herdando de `DomainError` (sem `ValueError` nativo)?
- [ ] O código foi submetido à revisão do Agente Avaliador e recebeu `[VEREDITO: APROVADO]`?
- [ ] Testes unitários foram criados ou atualizados para o novo caso de uso?
- [ ] Nenhum arquivo temporário ou binário de áudio foi versionado?
