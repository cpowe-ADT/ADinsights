# Frontend Shell

React + Vite shell for the multi-tenant analytics dashboard.

## Getting Started

```bash
npm install
npm run dev
```

The dev server will run on <http://localhost:5173>.

### Authentication flow

- Use valid tenant credentials to authenticate against `POST /api/auth/login/`.
- The React auth provider stores the returned SimpleJWT pair, exposes the current `tenant_id`, and schedules refreshes through `POST /api/auth/refresh/`.
- Once authenticated the dashboard requests metrics from `GET /api/campaign-metrics/` with the active bearer token. Loading, error, and empty states are surfaced across the grid and parish map.
- Select **Log out** from the header to clear tenant context and return to the login screen.

## Libraries

- **TanStack Table** for the analyst grid experience.
- **Leaflet / React-Leaflet** for the parish choropleth map.
- **Zustand** to coordinate shared state (selected metric, parish, API status).

## Testing

Run the Vitest suite, which now includes integration coverage for the login flow and tenant-scoped rendering:

```bash
npm test
```
