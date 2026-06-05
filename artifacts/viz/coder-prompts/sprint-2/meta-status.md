# Meta Status Page — Verification Only (No Viz Needed)

**Sprint:** 2
**Estimated size:** XS
**Depends on:** none
**Blocks:** nothing
**Role needed:** frontend-engineer

## Context

`MetaStatusPage` at `/dashboards/meta/status` shows Meta connection health — OAuth status, sync timestamps, error messages. It is a diagnostic/ops page, not an analytics page. No KPI charts, no trend lines, no combined endpoint call. This ticket's only job is to verify that the page does NOT accidentally fire `/api/metrics/combined/` and add a test to assert that invariant.

## Inputs already in the repo (do not re-invent)

- `frontend/src/routes/MetaStatusPage.tsx` (or equivalent path): existing file. A4 synthesis confirmed routes M8–M11 as clean.
- `frontend/src/components/EmptyState.tsx`: use if a no-connection state is not already handled.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/routes/__tests__/MetaStatusPage.test.tsx` (create if absent)

- **DO NOT modify the route file** unless you find an actual bug.

## What to check

1. Open `frontend/src/routes/MetaStatusPage.tsx` (or the real file path — look for the file that handles `/dashboards/meta/status`).
2. Confirm no import of `useDashboardStore.loadAll` and no fetch to `/api/metrics/combined/`.
3. If clean, add the test below. If not clean, fix the call and add the test.

## Test delta

File: `frontend/src/routes/__tests__/MetaStatusPage.test.tsx`

```typescript
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import * as apiClient from '../../lib/apiClient'  // adjust import path
import MetaStatusPage from '../MetaStatusPage'   // adjust import path

describe('MetaStatusPage — no combined call', () => {
  it('does NOT call /api/metrics/combined/ on mount', () => {
    const getSpy = vi.spyOn(apiClient, 'get')
    render(<MetaStatusPage />)
    const combinedCalls = getSpy.mock.calls.filter(([url]) =>
      typeof url === 'string' && url.includes('/metrics/combined')
    )
    expect(combinedCalls.length).toBe(0)
  })
})
```

## Definition of Done

- [ ] Test added asserting no `/api/metrics/combined/` call from MetaStatusPage
- [ ] If a bug was found and fixed, describe it in a code comment above the fix
- [ ] Tests green: `cd frontend && npm test -- --run src/routes/__tests__/MetaStatusPage.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Out of scope

- Do NOT add any chart components to this page
- Do NOT redesign the status page layout
