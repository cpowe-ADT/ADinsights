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
- Once authenticated the dashboard requests metrics from `GET /api/metrics/` with the active bearer token. Loading, error, and empty states are surfaced across the grid and parish map.
- Use the `VITE_MOCK_MODE` toggle in your `.env` file to switch between the local mock data fixtures (`true`) and the live API (`false`). The default is `false` so the shell now targets live `/api/*` routes unless explicitly overridden.
- Set `VITE_MOCK_ASSETS=true` when you also want to serve GeoJSON and other static fixtures from `frontend/public/`; otherwise those assets are requested from the API.
- Home page links can be overridden with `VITE_DOCS_URL`, `VITE_DOCS_CSV_URL`, and `VITE_RELEASE_NOTES_URL`.
- The home announcement banner is configurable via `VITE_HOME_ANNOUNCEMENT_ENABLED`, `VITE_HOME_ANNOUNCEMENT_ID`, `VITE_HOME_ANNOUNCEMENT_TITLE`, `VITE_HOME_ANNOUNCEMENT_MESSAGE`, `VITE_HOME_ANNOUNCEMENT_CTA_LABEL`, and `VITE_HOME_ANNOUNCEMENT_HREF`.
- Recent dashboards load from `GET /api/dashboards/recent/?limit=3`; when `VITE_MOCK_ASSETS=true`, the UI uses `frontend/public/mock/recent_dashboards.json` instead.
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
