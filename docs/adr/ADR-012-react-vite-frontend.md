# ADR-012 — React + Vite + Tailwind + shadcn/ui Frontend

| Field | Value |
|-------|-------|
| Date | 2024-01 |
| Status | Accepted |
| Deciders | Akshay |

## Context

TradeWatch needs a web UI for: viewing signals by date, managing alerts, running backtests, and configuring settings. The frontend will be served locally alongside the FastAPI backend.

## Decision

Use React 18 + Vite + Tailwind CSS + shadcn/ui for the frontend. State management via React Query (server state) and local `useState` (UI state).

## Rationale

- **Vite**: near-instant HMR, fast builds; significantly better DX than CRA
- **Tailwind CSS**: utility-first, no custom CSS files needed; consistent light theme
- **shadcn/ui**: pre-built, accessible components (Button, Card, Input, etc.) that are copied into the project — no runtime dependency; customizable
- **React Query**: handles server state (loading, error, cache invalidation) cleanly; avoids manual `useEffect` fetch boilerplate
- **Recharts**: lightweight chart library; sufficient for the backtest bar chart visualization
- **Light theme**: matches a professional trading tool aesthetic; avoids dark theme contrast issues on external displays

## Stack Details

```
npm create vite@latest . -- --template react
npm install tailwindcss @tailwindcss/vite
npm install @radix-ui/react-slot class-variance-authority clsx tailwind-merge lucide-react
npm install axios @tanstack/react-query react-router-dom recharts
```

Tailwind v4 with `@tailwindcss/vite` plugin — no separate `tailwind.config.js` required.

## Consequences

- Frontend is a separate `npm` project in `frontend/` — `start.sh` runs both `uvicorn` and `npm run dev`
- Vite dev server proxies `/api` to `http://localhost:8000` — no CORS issues during development
- shadcn/ui components are copied into `src/components/ui/` — they can be modified freely

## Alternatives Considered

- **Next.js**: rejected — SSR adds complexity; single-user local app doesn't need it; Vite is faster for development
- **Svelte / SvelteKit**: considered — excellent performance; rejected because team familiarity is higher with React
- **Plain HTML + Alpine.js**: rejected — insufficient for the alert table, backtest chart, and modal complexity
