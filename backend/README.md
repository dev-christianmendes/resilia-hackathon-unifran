# Backend — CITY TWIN / RESILIA

API FastAPI responsável por publicar a cidade, executar o motor de simulação, precificar intervenções, otimizar um portfólio por orçamento e responder ao Urban Copilot.

## Executar

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Healthcheck: `GET /api/health`
- Swagger: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Testar e verificar

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --explicit-package-bases app
```

## Módulos

| Caminho | Responsabilidade |
| --- | --- |
| `app/main.py` | Criação do FastAPI, CORS e configuração |
| `app/api/routes.py` | Endpoints HTTP |
| `app/schemas.py` | Requests/responses Pydantic |
| `app/data/franca.py` | Montagem da cidade |
| `app/data/fixtures/franca/` | Fixtures geoespaciais e fontes |
| `app/engine/simulation.py` | Risco, impactos e comparação |
| `app/engine/interventions.py` | Catálogo e normalização |
| `app/engine/costs.py` | Hipóteses e precificação |
| `app/engine/optimize.py` | Otimização por ganho esperado/orçamento |
| `app/ai/copilot.py` | Recomendação heurística e integração LLM |

## Dados e premissas

A cidade é carregada em memória a partir dos fixtures de Franca/SP. O motor usa um modelo determinístico/heurístico para combinar intensidade, duração, impermeabilidade, vegetação, elevação, proximidade de água, vulnerabilidade, infraestrutura e intervenções.

Os custos são hipóteses de ordem de grandeza e são publicados por `/api/costs/catalogue`. O resultado não é orçamento de obra, previsão de inundação ou recomendação operacional.

## Configuração do Copilot

Sem configuração, o backend usa a heurística offline. Para habilitar um provedor compatível com a API da OpenAI:

```bash
export URBAN_COPILOT_API_KEY='...'
export URBAN_COPILOT_BASE_URL='https://api.openai.com/v1'
export URBAN_COPILOT_MODEL='gpt-4o-mini'
```

Não registre chaves no Git. Consulte `backend/.env.example` para os nomes das variáveis e `../README.md` para o contrato completo da API.
