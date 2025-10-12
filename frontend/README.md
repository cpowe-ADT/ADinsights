# Frontend Shell

React + Vite shell prepared for the analytics dashboard.

## Getting Started

```bash
npm install
npm run dev
```

The dev server will run on <http://localhost:5173>. The map consumes `public/jm_parishes.json` and the grid loads `public/sample_metrics.json` until backend APIs are ready.

## Libraries

- **TanStack Table** for the analyst grid experience.
- **Leaflet / React-Leaflet** for the parish choropleth map.
- **Zustand** to coordinate shared state (selected metric, parish).

Swap the mock fetches in `useDashboardStore` with real API endpoints once the backend is live.
