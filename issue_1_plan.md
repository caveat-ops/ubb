# Análise e Planejamento da Issue #1: Certification Tracks

## Resumo da Issue

**User Story:** Como estudante do UBB, desejo criar uma trilha de treinamento personalizada para certificações (ex: Kubernetes Security Specialist - CKS) fazendo o upload do currículo em PDF do exame.

**Objetivos Principais:**
1. Permitir que o usuário faça upload de um PDF contendo o currículo do exame.
2. O sistema deve analisar o PDF, extrair os tópicos do exame.
3. O sistema deve buscar na base de conhecimento (posts indexados) os materiais relevantes para cada tópico.
4. Estruturar os materiais por nível de dificuldade (do fácil ao difícil).
5. Informar claramente os tópicos que **não** possuem materiais na base de dados.
6. Fornecer uma visão geral na forma de tabela, mostrando o percentual de cobertura (`Content Covered`) de diferentes exames.

---

## Plano de Execução (Sub-Issues)

Para implementar esta funcionalidade de forma iterativa e modular, a Issue #1 será dividida nas seguintes sub-issues:

### 1. Sub-Issue 1: Processamento de PDF e Extração de Tópicos (Backend)
**Objetivo:** Receber o PDF do currículo, extrair o texto e utilizar LLM para identificar os tópicos de estudo exigidos.
- **Tarefas:**
  - Adicionar dependência para leitura de PDF no `requirements.api.txt` (ex: `pdfplumber` ou `PyPDF2`).
  - Criar um novo serviço em `backend/app/services/pdf_processor.py` (ou similar) para lidar com a extração de texto de PDFs.
  - Integrar com o LLM (Ollama/modelo local já existente) enviando o texto do PDF com um prompt específico para extrair os tópicos e retorná-los num formato estruturado (ex: JSON).
  - Criar modelos Pydantic no `schemas.py` para representar os tópicos extraídos.

### 2. Sub-Issue 2: Modelagem de Dados para Trilhas de Certificação (Backend)
**Objetivo:** Criar tabelas no banco de dados para salvar as trilhas geradas pelos usuários.
- **Tarefas:**
  - Atualizar o `backend/app/models.py` criando as tabelas necessárias:
    - `CertificationExam`: Para armazenar dados gerais do exame (nome, PDF, etc).
    - `CertificationTrack`: Para ligar um usuário a uma trilha gerada.
    - `TrackTopic`: Para armazenar os tópicos específicos e seu status de cobertura (se tem material ou não).
    - `TrackMaterial`: Para associar posts (`Post`) a um `TrackTopic`.
  - Gerar e aplicar as migrações (se estiver usando Alembic) ou garantir que as tabelas sejam criadas no startup (`Base.metadata.create_all`).

### 3. Sub-Issue 3: Busca e Associação de Materiais (Backend)
**Objetivo:** Realizar o match entre os tópicos extraídos do currículo e os materiais da base de dados usando busca vetorial.
- **Tarefas:**
  - Gerar embeddings para cada tópico extraído (utilizando a mesma solução de embeddings dos posts).
  - Fazer uma query de busca por similaridade (Vector Search usando `pgvector`) na tabela `posts` para cada tópico.
  - Definir um threshold de similaridade. Se nenhum post atingir o threshold, marcar o tópico como ausente (missing).
  - Para os posts encontrados, ordená-los pelo campo `difficulty` (do fácil ao difícil). Se o campo `difficulty` estiver vazio, criar uma lógica de ordenação padrão (ex: por data ou tamanho do texto).
  - Calcular o percentual de cobertura (`Content Covered`) baseado na proporção de tópicos com pelo menos um material encontrado.

### 4. Sub-Issue 4: Endpoints da API para Trilhas (Backend)
**Objetivo:** Expor a funcionalidade para o frontend via API REST.
- **Tarefas:**
  - Criar um novo router em `backend/app/routers/tracks.py`.
  - Endpoint `POST /api/tracks/upload`: Recebe o arquivo PDF via `UploadFile`, executa o pipeline (Sub-Issue 1 e 3), salva no banco (Sub-Issue 2) e retorna os dados estruturados da trilha.
  - Endpoint `GET /api/tracks`: Retorna as trilhas do usuário com o progresso e percentual de cobertura.
  - Endpoint `GET /api/tracks/{track_id}`: Retorna os detalhes de uma trilha específica (tópicos, materiais e tópicos ausentes).
  - Adicionar o router no `main.py`.

### 5. Sub-Issue 5: Interface de Upload e Visão Geral (Frontend)
**Objetivo:** Criar as telas no frontend para o usuário submeter PDFs e visualizar seus exames.
- **Tarefas:**
  - Criar a página `/tracks` no Next.js (`frontend/app/tracks/page.tsx`).
  - Implementar o componente de formulário para upload de arquivos (drag & drop ou input file).
  - Implementar estados de carregamento (loading spinners/progress bar) pois o processamento do PDF + LLM + Vector Search pode demorar.
  - Implementar a tabela sugerida mostrando o progresso:
    `| Exam | Content Covered | Link to training material |`

### 6. Sub-Issue 6: Visualização Detalhada da Trilha (Frontend)
**Objetivo:** Mostrar os detalhes da trilha de um exame específico, dividida por tópicos e nível de dificuldade.
- **Tarefas:**
  - Criar a página de detalhes da trilha (ex: `/tracks/[id]/page.tsx`).
  - Renderizar os materiais disponíveis organizados em formato de base de conhecimento (Knowledge Base format).
  - Implementar UI/UX para alertar claramente o usuário sobre os tópicos que estão faltando (missing topics) para que ele busque fora da plataforma.
  - Implementar um design indicando o nível de dificuldade (ex: badges "Fácil", "Intermediário", "Difícil") em cada material.

### 7. Sub-Issue 7: Integração com Framework TIERS (Melhoria Futura)
**Objetivo:** Implementar a sugestão de organizar/testar o conteúdo por certificação usando o framework TIERS.
- **Tarefas:**
  - Analisar a estrutura do TIERS.
  - Adicionar campos de metadados nos modelos ou tags específicas (`tiers_level`) aos materiais e trilhas.
  - Criar filtros adicionais na UI para ordenar/visualizar o conteúdo sob a ótica da metodologia TIERS.
