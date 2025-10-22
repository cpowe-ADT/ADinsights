# Frontend Design System & UX Implementation Plan

**Role Assumed:** Senior frontend architect & design systems lead  
**Repository:** `cpowe-ADT/ADinsights` (React + Vite frontend, Django/DRF backend)  
**Target:** WCAG 2.1 AA, multi-tenant theming, alignment with Figma (`<PASTE_PUBLIC_VIEW_LINK>` — update once real link is provided)

This plan decomposes the requested deliverables into executable work packages. Each package should be tracked as its own epic/issue, scoped to the `frontend/` folder (plus docs/config as needed) in keeping with AGENTS guardrails.

---

## Phase F0 – Discovery & Foundations (Week 0)

1. **Confirm design source**
   - Request actual Figma public link + component library page references.
   - Export typography scale, spacing, color palette, motion specs.
2. **Audit existing frontend**
   - Inventory current CSS modules, inline styles, and shared components.
   - Identify hard-coded colors/numbers for refactor backlog.
3. **Decide toolchain**
   - Confirm Tailwind adoption (vs. CSS modules + Design Tokens). Given requirements, plan to integrate Tailwind alongside CSS variables.

Deliverable: short tech-spec (Google Doc or repo ADR) confirming decisions + migration order.

---

## Phase F1 – Tokens & Theming (Weeks 1–2)

1. **Design Tokens**
   - Create `frontend/src/design/tokens.json` (DTCG-like structure) with primitive + semantic tokens: colors (brand, surfaces, text, status), typography scale (font families, sizes, line heights), spacing (4/8px steps), radii, shadows, z-index, motion durations/curves.
   - Define brand-neutral default; allow overrides via tenant brand theme.
2. **CSS Variables**
   - Generate `frontend/src/styles/foundations.css` using tokens → CSS custom properties for `:root` (light) and `[data-theme="dark"]`.
   - Include `[data-tenant="<id>"]` hook for optional brand overrides (colors only).
3. **Semantic Mapping**
   - Establish naming: e.g., `--color-bg-canvas`, `--color-bg-elevated`, `--color-fg-muted`, `--color-brand-500`, `--color-status-success`, etc.
   - Document usage in `docs/design-system.md`.

Acceptance Gate: No component should reference raw hex/spacing once Phase F1 completes.

---

## Phase F2 – Build Setup & Linting (Weeks 2–3)

1. **Tailwind Integration**
   - Install `tailwindcss`, `postcss`, `autoprefixer`.
   - Configure `tailwind.config.ts` to read CSS variables (`extend.colors`, `spacing`, `borderRadius`, `boxShadow`, `zIndex`, `fontSize`).
   - Wire PostCSS plugins into Vite.
2. **Linting & Formatting**
   - Add/extend ESLint (typescript + react), eslint-plugin-jsx-a11y, Prettier, Stylelint (enforce token usage, disallow raw hex).
   - Add scripts: `npm run lint`, `npm run format:check`, `npm run stylelint`.
3. **CI prep**
   - Draft GitHub Actions workflow to run lint/checks (activate in Phase F7).

---

## Phase F3 – Component System (Weeks 3–6)

Break into smaller epics per component cluster. Each component leverages semantic tokens, Tailwind utilities, and exposes light/dark stories.

1. **Primitives**
   - Button, IconButton, Badge, Tooltip (accessible), Input, Select, Checkbox, Radio, Textarea.
   - Variants: primary/secondary/ghost/link/destructive; sizes sm/md/lg; states disabled, focus, hover, loading.
2. **Feedback & Layout**
   - Tabs, Accordion, Dialog/Drawer, Toast/Alert, Card, Skeleton, EmptyState.
3. **Navigation**
   - Navbar, Sidebar, Breadcrumbs, FilterBar, TenantSwitcher shell.
4. **Data Display**
   - Table wrapper around TanStack Table (tokenized), KPI Tile, Chart container with theming hooks.
5. **Storybook**
   - Install Storybook 8; create stories for each component (light + dark + all states). Enable Storybook test runner.

Acceptance Gates:

- Components consume tokens only; pass Axe accessibility audit.
- Stories documented with controls/args and usage notes.

---

## Phase F4 – Data Visualization & Maps (Weeks 6–7)

1. **Chart Theme**
   - Define palette (series, axis, grid, tooltip) based on tokens for both themes.
   - Implement chart wrappers using theme (e.g., Recharts/Victory/d3 wrappers).
2. **Leaflet Choropleth**
   - Tokenize fills/hover/selection colors.
   - Add keyboard navigation + focus-visible styling; ensure legend uses tokens.
3. **KPI Tiles & Grids**
   - Align spacing/typography to Figma within ±2px; responsive layout using CSS grid.

---

## Phase F5 – Layout Templates & Board Pack (Weeks 7–8)

1. **Layouts**
   - Dashboard, Reports, Data Sources, Alerts, Users/Roles, Billing templates with consistent 8px spacing, gutters, and max-width.
2. **Board Pack Printable View**
   - Build `/board-pack` view with print stylesheet (A4/Letter), header/footer, timestamp watermark, aggregated KPIs. Hook `window.print()`.

Acceptance Gate: Dashboard + one additional page match Figma metrics ±2px.

---

## Phase F6 – Multi-tenant UX Hooks (Weeks 8–9)

1. **Tenant Context**
   - Implement Tenant Switcher shell (mock API until backend ready). Ensure assets filtered by context.
2. **Per-tenant Branding**
   - Support `[data-tenant="<id>"]` overrides from backend config (color accents only).

---

## Phase F7 – Accessibility, Motion & Quality Gates (Weeks 9–10)

1. **A11y**
   - Ensure focus-visible rings, aria labels, and color contrast (≥4.5:1) across components.
   - Provide `prefers-reduced-motion` fallbacks for transitions/charts.
2. **Testing & CI**
   - Integrate Storybook visual regression (Chromatic or Playwright screenshot diff).
   - Add GitHub Actions workflow running lint, type-check, Storybook tests, Axe (React Testing Library + jest-axe).
3. **Lighthouse Budgets**
   - Configure Lighthouse CI with LCP/CLS budgets; add to CI.

Acceptance Gate: CI blocks on lint, a11y, and visual diff failures.

---

## Phase F8 – Performance Optimisations (Weeks 10–11)

- Route-level lazy loading (React.lazy/Suspense) for heavy pages.
- Chart library code-splitting; ensure icon libraries tree-shake.
- Preload fonts with `font-display: swap`; evaluate bundling fonts locally if allowed.
- Optimise images (responsive sizes, compression).

---

## Phase F9 – Backend Integration Toggle & Docs (Weeks 11–12)

1. **Integration Toggle**
   - Ensure `VITE_MOCK_MODE` toggling requires no code change. Add script to switch to `/api/*` endpoints.
   - Document metrics endpoint contracts (shape, required fields) in `docs/design-system.md` or `docs/api/frontend-metrics.md`.
2. **Documentation**
   - Author `docs/design-system.md`: token taxonomy, component APIs, theming rules, dark mode usage, export guidelines.
   - Author `docs/migration-guide.md`: converting legacy pages to tokens/components, search/replace hints, lint rules.

---

## Dependencies & Coordination

- Coordinate with backend team on tenant context API + metrics contract.
- Ensure design tokens align with final Figma library (need actual link and measurement notes).
- For visual regression baseline, capture initial Storybook snapshots post-Phase F3.

## Risk & Mitigation

- **Missing Figma link:** request ASAP; otherwise, use placeholder tokens subject to redesign.
- **Team adoption:** plan enablement sessions, pair with feature SMEs to convert first pages together.
- **Regression risk:** rely on Storybook visual tests + ESLint/Stylelint token enforcement.

## Questions / Inputs Needed

1. Provide the actual Figma public view link and confirm version to reference.
2. Confirm charting library preference (existing or migrating).
3. Clarify whether Tailwind adoption has constraints (e.g., design team preference).
4. Decide on visual regression tool (Chromatic SaaS vs in-house Playwright).

Please update this plan as timelines shift or new requirements surface.
