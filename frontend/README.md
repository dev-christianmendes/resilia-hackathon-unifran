# CITY TWIN / RESILIA

Frontend React + TypeScript + Vite do digital twin de Franca/SP. A interface guia o usuário por quatro passos: **Observar → Simular → Mitigar → Comparar**.

## Rodando localmente

```bash
npm install
npm run dev
```

O Vite usa `http://localhost:8000` como proxy padrão para a API. Para outro endereço:

```bash
VITE_API_PROXY=http://localhost:8010 npm run dev
```

Checks de entrega:

```bash
npm run typecheck
npm run lint
npm run build
```

## Estrutura

- `src/App.tsx`: shell responsivo, stepper, estados de carregamento/erro, tutorial e layout do mapa.
- `src/components/ui.tsx`: componentes reutilizáveis de painel, botão, slider, selo de risco, legenda, tooltip e stepper.
- `src/components/CityScene.tsx`: cena 3D, seleção, foco suave da câmera, risco territorial e labels contextuais.
- `src/components/CityGeometry.tsx`: edifícios, vias, vegetação e cursos d’água.
- `src/panels/`: conteúdo das etapas e detalhe contextual de região.
- `src/state/`: reducer e hook `useCityTwin`, mantendo o estado centralizado.
- `src/lib/`: cliente HTTP, geometria, tema, cores e formatação.

## Decisões de UX

Labels de todas as regiões não ficam mais fixos no mapa. Apenas a seleção, o hover e até sete regiões críticas aparecem; nomes repetidos de cursos d’água são agrupados apenas para exibição. A cor do território comunica risco depois da simulação e a legenda fica sempre visível.

O mapa recebe `waterways` diretamente de `/api/city`, sem modificar o contrato do backend. Os cursos d’água são desenhados como linhas leves e associam sua cor ao risco da região mais próxima. Os números exibidos são estimativas da POC e não substituem dados oficiais.

O tour inicial usa `localStorage` (`resilia-tour-seen`) e pode ser reaberto pelo botão **Tutorial**. Não há dependências novas de UI, tour ou mapas.
