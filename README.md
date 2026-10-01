# CITY TWIN — RESILIA

Digital twin urbano para explorar a resiliência de Franca/SP diante de chuva extrema e onda de calor. A POC permite observar o território, simular um evento, testar intervenções e comparar estimativas antes/depois.

> **Importante:** todos os números são estimativas do modelo da POC. Não são previsões operacionais e não substituem dados oficiais, estudos hidráulicos, dimensionamento de obras ou decisões da Defesa Civil.

## Visão rápida

O produto é um monorepo com:

- **Frontend:** mapa 3D interativo, fluxo guiado em quatro etapas, seleção de regiões, risco territorial, mitigação, comparação e Urban Copilot.
- **Backend:** API FastAPI com dados geoespaciais de Franca, motor determinístico de simulação, catálogo de intervenções, otimização por orçamento e Copilot heurístico/LLM opcional.
- **Dados:** fixtures versionadas em `backend/app/data/fixtures/franca/`, carregadas em memória. Não há banco de dados ou persistência de cenários.

Fluxo da interface: **Observar → Simular → Mitigar → Comparar**.

## Stack

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 19, TypeScript estrito, Vite, Tailwind CSS 4, React Three Fiber, drei, three |
| Backend | Python 3.10+, FastAPI, Pydantic v2, Uvicorn |
| Qualidade | pytest, pytest-asyncio, ruff, mypy, oxlint, TypeScript |
| Deploy local | Docker Compose, Nginx para servir o frontend |

## Requisitos

- Node.js compatível com o Vite atual e npm.
- Python 3.10 ou superior.
- Docker e Docker Compose apenas para execução conteinerizada.

## Executar localmente

### 1. Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verifique a API:

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok"}
```

A documentação interativa fica em <http://127.0.0.1:8000/docs>.

### 2. Frontend

Em outro terminal:

```bash
cd frontend
npm ci
npm run dev
```

Acesse <http://localhost:5173>. O proxy do Vite envia `/api` para `http://localhost:8000`.

Para usar outra porta ou host:

```bash
VITE_API_PROXY=http://127.0.0.1:8010 npm run dev
```

### Docker Compose

```bash
docker compose up --build
```

| Serviço | URL |
| --- | --- |
| Aplicação | <http://localhost:8080> |
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |

O frontend aguarda o healthcheck do backend antes de iniciar.

## Configuração

Copie `backend/.env.example` para `backend/.env` quando precisar personalizar o ambiente. O backend carrega esse arquivo via `python-dotenv`.

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Origens permitidas pelo backend, separadas por vírgula |
| `URBAN_COPILOT_API_KEY` | vazio | Chave opcional de um provedor compatível com a API da OpenAI |
| `URBAN_COPILOT_BASE_URL` | vazio | Base URL do provedor LLM |
| `URBAN_COPILOT_MODEL` | vazio | Nome do modelo |
| `VITE_API_PROXY` | `http://localhost:8000` | Destino do proxy `/api` no desenvolvimento |

Sem as três variáveis do Copilot, a aplicação usa a análise heurística offline. Falhas no provedor também retornam à heurística; a interface identifica a fonte da recomendação.

## API

Todas as rotas abaixo usam o prefixo `/api`. Os schemas completos estão em `backend/app/schemas.py` e podem ser explorados em `/docs`.

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/health` | Healthcheck |
| `GET` | `/city` | Cidade, regiões, vias, cursos d’água, equipamentos, edificações, árvores, relevo e fontes |
| `GET` | `/scenarios` | Cenários disponíveis e impactos descritos |
| `GET` | `/interventions/catalogue` | Tipos de intervenção, descrição, efeitos e fator padrão |
| `GET` | `/costs/catalogue` | Hipóteses de custo publicadas pelo modelo |
| `POST` | `/simulate` | Uma simulação com zero ou mais intervenções |
| `POST` | `/compare` | Comparação de uma configuração com o baseline |
| `POST` | `/run` | Baseline, resultado mitigado, comparação e custo em uma resposta atômica |
| `POST` | `/optimize` | Portfólio de intervenções dentro de um orçamento |
| `POST` | `/copilot` | Recomendação explicável para o cenário atual |

### Exemplo de simulação

```bash
curl -s http://localhost:8000/api/simulate \
  -H 'content-type: application/json' \
  -d '{
    "scenario": {
      "type": "extreme_rain",
      "intensity": 0.8,
      "duration": 0.6
    },
    "interventions": []
  }' | python3 -m json.tool
```

`intensity`, `duration` e `impact_factor` são números entre `0` e `1`. Os tipos de cenário são `extreme_rain` e `heat_wave`; os tipos de intervenção estão no catálogo.

### Formato de `/api/city`

O payload inclui `regions`, `roads`, `waterways`, `facilities`, `buildings`, `trees`, `boundary`, `elevation`, `vulnerability_points` e `sources`. Cada região possui geometria, centroide, métricas ambientais/sociais, quantidade de vias e equipamentos associados.

Os cursos d’água têm `id`, `name` opcional, `kind`, `path`, `width_m` e origem. O frontend agrupa somente o nome para exibição; IDs e geometrias continuam distintos.

## Desenvolvimento e qualidade

Backend:

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --explicit-package-bases app
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

Para validar a integração manualmente, suba backend e frontend e percorra: selecionar região → simular → adicionar intervenção → re-simular → comparar.

## Estrutura do repositório

```text
backend/
  app/
    api/routes.py             rotas REST
    schemas.py                contratos Pydantic da API
    ai/copilot.py             heurística e LLM opcional
    data/                     cidade e fixtures geoespaciais
    engine/                   simulação, custos, intervenções e otimização
    main.py                   FastAPI, CORS e configuração
  tests/                      testes do motor e da API
  Dockerfile
  pyproject.toml

frontend/
  src/
    App.tsx                   shell, etapas, tutorial e layout
    components/               mapa 3D, geometria e componentes UI
    panels/                   conteúdo contextual das etapas
    state/                    reducer e hook useCityTwin
    lib/                      API, geometria, tema e formatação
  Dockerfile
  vite.config.ts
  README.md
```

## Decisões e limitações conhecidas

- A cidade é baseada nos fixtures de Franca/SP e carregada em memória; não há persistência nem autenticação.
- O motor é determinístico e usa heurísticas para risco, vizinhança, custos e propagação de efeitos; não é um modelo hidráulico ou climático operacional.
- O frontend mantém o contrato do backend e evita dependências adicionais para UI, tour e mapas.
- A geometria 3D é otimizada com instancing em camadas repetitivas. Os cursos d’água são renderizados como linhas leves; uma fita de água animada é uma evolução futura.
- O banco de dados e PostGIS foram deliberadamente adiados. A próxima evolução natural é substituir o carregamento integral por consultas e versionamento de dados geoespaciais.
