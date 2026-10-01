# Frontend — CITY TWIN / RESILIA

Aplicação React que apresenta o digital twin de Franca/SP em uma cena 3D e conduz o usuário por quatro etapas:

1. **Observar:** explorar o mapa, consultar as regiões mais críticas e abrir o detalhe contextual.
2. **Simular:** escolher chuva extrema, onda de calor, granizo, ventania ou queimada de grande porte e ajustar intensidade/duração.
3. **Mitigar:** testar intervenções no mapa, acompanhar orçamento e pedir uma sugestão ao Urban Copilot.
4. **Comparar:** executar novamente o cenário e ler os deltas antes/depois.

## Desenvolvimento

```bash
npm ci
npm run dev
```

O Vite serve em <http://localhost:5173> e encaminha `/api` para `http://localhost:8000`. Altere o destino sem editar código:

```bash
VITE_API_PROXY=http://127.0.0.1:8010 npm run dev
```

Comandos disponíveis:

| Comando | Finalidade |
| --- | --- |
| `npm run dev` | Servidor Vite com hot reload |
| `npm run typecheck` | TypeScript sem emitir arquivos |
| `npm run lint` | Oxlint |
| `npm run build` | Typecheck + build de produção |
| `npm run preview` | Servir o build localmente |

## Arquitetura

- `src/App.tsx`: shell da aplicação, stepper, layout desktop/mobile, tutorial, estados de erro e carregamento.
- `src/components/CityScene.tsx`: Canvas, seleção, controles Orbit, labels contextuais, risco e placement.
- `src/components/CityGeometry.tsx`: edifícios, vias, vegetação e cursos d’água.
- `src/components/Terrain.tsx`: polígonos de região, elevação, contornos, seleção e coloração de risco.
- `src/components/ui.tsx`: `Panel`, `Button`, `Slider`, `RiskBadge`, `RiskLegend`, `Tooltip`, `Stepper` e estados vazios.
- `src/panels/`: etapas de simulação, mitigação, comparação, Copilot, regiões e camadas.
- `src/state/appState.ts`: reducer, pré-requisitos de etapa, seleção e staleness.
- `src/state/useCityTwin.ts`: carregamento da cidade, chamadas REST, orçamento, Copilot e otimização.
- `src/lib/api.ts`: cliente tipado da API sem alterar contratos do backend.

## Contrato usado pelo frontend

O cliente consome:

```text
GET  /api/city
GET  /api/interventions/catalogue
GET  /api/costs/catalogue
POST /api/run
POST /api/optimize
POST /api/copilot
```

`/api/run` é preferido para manter baseline, resultado mitigado, comparação e custo na mesma resposta. Os tipos correspondentes estão em `src/types.ts`; a fonte oficial dos schemas é `backend/app/schemas.py`.

## Decisões de UX e acessibilidade

- Só uma etapa de trabalho aparece no painel principal por vez.
- Comparar fica bloqueado até existir uma simulação e uma configuração mitigada reexecutada.
- O território usa verde, amarelo e vermelho para comunicar risco, sempre acompanhado de texto/ícone.
- Labels não ficam fixos em todos os polígonos: aparecem para seleção, hover e um conjunto reduzido de regiões críticas.
- Nomes com sufixos numéricos são agrupados somente na camada de apresentação.
- `waterways` é consumido diretamente de `/api/city`; a geometria não é modificada.
- Os labels de cursos d'água são limitados a nomes distintos e posicionados no ponto médio do traçado, reduzindo sobreposição.
- `drainage_clogging` é mostrado no detalhe regional e o mapa usa os riscos retornados pelo motor para colorir o território.
- Granizo, ventania e queimadas usam efeitos visuais leves, sem dependências adicionais; o risco detalhado continua vindo do backend.
- Controles têm foco visível, `aria-label` em sliders e navegação por teclado.
- `prefers-reduced-motion` reduz transições e animações.
- O tutorial inicial usa `localStorage` e pode ser reaberto pelo botão **Tutorial**.

Os números são estimativas da POC e não substituem dados oficiais.
