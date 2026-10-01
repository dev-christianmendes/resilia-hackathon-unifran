# CITY TWIN — RESILIA

Digital twin urbano para resiliência ao El Niño. Observar a cidade, simular eventos
climáticos extremos, testar intervenções de infraestrutura e comparar o antes e o depois.

> Os números são **estimativas produzidas pelo motor de simulação da POC**. Não são previsões
> operacionais nem substituem dados oficiais de defesa civil ou saneamento.

## O que a POC faz

- **Digital twin 3D** de uma cidade sintética determinística (6 regiões, malha viária,
  edificações, vegetação e equipamentos públicos) em React Three Fiber.
- **Cenários** de chuva extrema e onda de calor, com intensidade e duração ajustáveis.
- **Riscos** por região: população afetada, vias comprometidas, equipamentos críticos,
  susceptibilidade do terreno, impermeabilidade, cobertura vegetal e vulnerabilidade social.
- **Intervenções**: reservatório, abrigo, rota alternativa e ponto de atendimento, com fator
  de impacto ajustável por intervenção.
- **Comparação antes/depois** com deltas absolutos e percentuais, totais e por região,
  incluindo o efeito de transbordo entre regiões vizinhas.
- **Urban Copilot** que recebe o cenário simulado e devolve região priorizada, fatores de
  maior peso, intervenção sugerida e o efeito estimado — com heurística offline opcionalmente
  substituída por um LLM compatível com a API da OpenAI.

Fluxo de trabalho na tela: `OBSERVE → SIMULATE → MITIGATE`.

## Stack

| Camada | Tecnologias |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, React Three Fiber, drei, three |
| Backend | Python 3.10+, FastAPI, Pydantic v2, Uvicorn |
| Dados | Cidade sintética determinística em memória (seed `20240517`) |
| Testes | pytest, ruff, mypy, oxlint, tsc, Playwright (verificação manual do fluxo) |

O banco de dados é intencionalmente adiado: a POC carrega a cidade inteira em memória.
Trocar `backend/app/data/city.py` por consultas PostGIS é o próximo passo natural.

## Rodando localmente

Backend (porta 8000):

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Frontend (porta 5173, com proxy para `/api`):

```bash
cd frontend
npm ci
npm run dev
```

Acesse <http://localhost:5173>. Se o backend não estiver na porta 8000, aponte o proxy:

```bash
VITE_API_PROXY=http://127.0.0.1:8765 npm run dev
```

Documentação interativa da API: <http://localhost:8000/docs>.

### Com Docker

```bash
docker compose up --build
```

- App: <http://localhost:8080>
- API: <http://localhost:8000> (docs em `/docs`)

## Urban Copilot

Sem configuração, o Copilot roda em modo **heurístico** e totalmente offline. Para usar um
modelo compatível com a API da OpenAI, exporte as variáveis antes de subir o backend:

```bash
export URBAN_COPILOT_API_KEY=sk-...
export URBAN_COPILOT_BASE_URL=https://api.openai.com/v1
export URBAN_COPILOT_MODEL=gpt-4o-mini
```

Se qualquer uma faltar ou a chamada falhar, o backend registra o erro e devolve a análise
heurística — a POC nunca fica sem resposta.

## Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Origens liberadas no CORS |
| `URBAN_COPILOT_API_KEY` | vazio | Chave da API do LLM |
| `URBAN_COPILOT_BASE_URL` | vazio | Base URL compatível com OpenAI |
| `URBAN_COPILOT_MODEL` | vazio | Identificador do modelo |
| `VITE_API_PROXY` | `http://localhost:8000` | Backend usado pelo proxy do Vite |

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/health` | Verificação de saúde |
| `GET` | `/api/city` | Cidade completa com regiões, vias, edificações, árvores e equipamentos |
| `GET` | `/api/scenarios` | Cenários disponíveis e parâmetros |
| `GET` | `/api/interventions/catalogue` | Catálogo de intervenções e fatores padrão |
| `POST` | `/api/simulate` | Executa um cenário com um conjunto de intervenções |
| `POST` | `/api/compare` | Compara dois resultados e devolve deltas por região |
| `POST` | `/api/copilot` | Análise explicável do cenário corrente |

Exemplo:

```bash
curl -s http://localhost:8000/api/simulate \
  -H 'content-type: application/json' \
  -d '{"scenario": {"type": "extreme_rain", "intensity": 0.8, "duration": 0.6},
       "interventions": [
         {"id": "int-1", "type": "reservoir", "region_id": "region-02",
          "location": {"x": 0, "y": 0, "lat": null, "lng": null},
          "impact_factor": 1.0, "created_at": "2024-05-17T00:00:00Z"}
       ]}' | python -m json.tool
```

## Qualidade

```bash
# backend
cd backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy --explicit-package-bases app

# frontend
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Estrutura

```
backend/
  app/
    api/routes.py       endpoints REST
    ai/copilot.py       heurística + LLM opcional
    data/city.py        gerador da cidade sintética
    engine/             motor de simulação e intervenções
    main.py             app FastAPI e CORS
  tests/                pytest (35 testes)
frontend/
  src/
    components/         cena 3D e primitivos de UI
    lib/                cliente HTTP, geo, tema
    panels/             Cenário, Região, Mitigação, Comparação, Copilot, Camadas
    state/              reducer e hook `useCityTwin`
```

## Limitações conhecidas

- Cidade sintética: não usa dados reais de chuva, solo ou população.
- Propagação de enchente entre regiões é heurística (distribuição por vizinhança), não
  hidráulica.
- Sem persistência: reiniciar o backend descarta o cenário.
- O LLM do Copilot é opcional e recebe apenas o resumo do cenário, nunca geometria completa.
