# AccessibleTableToggle Component

**Sprint:** 1
**Estimated size:** S
**Depends on:** none
**Blocks:** TrendLine, DistributionBar, BubbleScatter, PieComposition
**Role needed:** frontend-engineer

## Context

`AccessibleTableToggle` provides a toggle button that switches between a chart view and a semantically-equivalent `<table>` view of the same data. This is required for WCAG AA compliance — every chart must have a non-chart equivalent that screen readers and keyboard users can navigate. It wraps any chart node and any table node; only the active view is visible, but both are in the DOM (inactive is `aria-hidden`).

## Inputs already in the repo (do not re-invent)

- None specific. Uses only React and standard DOM/ARIA.

## Deliverable

- **File(s) to create/modify**:
  - `frontend/src/components/viz/AccessibleTableToggle.tsx` (create)
  - `frontend/src/components/viz/__tests__/AccessibleTableToggle.test.tsx` (create)

- **Props API**:

```typescript
interface AccessibleTableToggleProps {
  chartNode: React.ReactNode;
  tableNode: React.ReactNode;
  defaultView?: 'chart' | 'table'; // default: 'chart'
  label?: string; // accessible label for the toggle button, default: 'Switch to table view'
  className?: string;
}
```

- **Data binding**: none — wraps pre-rendered nodes.

- **Interactions**:
  - Toggle button switches between chart and table views
  - Keyboard: tab reaches button, Enter or Space toggles
  - Both views are mounted; inactive view has `aria-hidden="true"` and `style={{ display: 'none' }}` (display:none removes from tab order AND from accessibility tree)

- **Empty/loading/error states**: none — delegates to child nodes.

- **A11y**:
  - Toggle button: `aria-pressed` reflects current state. When showing table: `aria-pressed="true"` and label changes to "Switch to chart view". When showing chart: `aria-pressed="false"` and label is "Switch to table view".
  - The table node should be a semantically correct `<table>` with `<thead>`, `<tbody>`, `<th scope="col">`.
  - Focus moves to the newly-visible view's first focusable element after toggle (use `useRef` + `focus()` call in a `useEffect`).

## Design

```
┌─────────────────────────────────────────────────────┐
│                  [Chart / Table icon button]         │ ← positioned top-right
│  ┌───────────────────────────────────────────────┐  │
│  │  Chart view (or aria-hidden table)            │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Button icon: use text label "Table" / "Chart" — do NOT assume any icon library is available unless you confirm it in `frontend/package.json`.

## Definition of Done

- [ ] Toggle button switches between chart and table views
- [ ] Inactive view is `aria-hidden="true"` and `display: none`
- [ ] `aria-pressed` state updates on toggle
- [ ] Keyboard: tab to button, Enter/Space toggles — verified by `@testing-library/user-event`
- [ ] Focus moves to first element of newly-shown view after toggle
- [ ] jest-axe passes for both states
- [ ] Tests green: `cd frontend && npm test -- --run src/components/viz/__tests__/AccessibleTableToggle.test.tsx`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Build clean: `cd frontend && npm run build`

## Test deltas

File: `frontend/src/components/viz/__tests__/AccessibleTableToggle.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'jest-axe'
import { AccessibleTableToggle } from '../AccessibleTableToggle'

const Chart = () => <div data-testid="chart">Chart</div>
const TableView = () => (
  <table>
    <thead><tr><th scope="col">Date</th><th scope="col">Value</th></tr></thead>
    <tbody><tr><td>2026-01-01</td><td>100</td></tr></tbody>
  </table>
)

describe('AccessibleTableToggle', () => {
  it('shows chart by default', () => {
    render(<AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />)
    expect(screen.getByTestId('chart')).toBeVisible()
  })

  it('toggles to table view on button click', async () => {
    const user = userEvent.setup()
    render(<AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />)
    await user.click(screen.getByRole('button'))
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByTestId('chart')).not.toBeVisible()
  })

  it('toggles back to chart view', async () => {
    const user = userEvent.setup()
    render(<AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />)
    const btn = screen.getByRole('button')
    await user.click(btn)
    await user.click(btn)
    expect(screen.getByTestId('chart')).toBeVisible()
  })

  it('button is keyboard-operable', async () => {
    const user = userEvent.setup()
    render(<AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />)
    await user.tab()
    expect(screen.getByRole('button')).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('table')).toBeVisible()
  })

  it('inactive view is aria-hidden', () => {
    render(<AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />)
    const tableContainer = screen.getByRole('table').closest('[aria-hidden]')
    expect(tableContainer).toHaveAttribute('aria-hidden', 'true')
  })

  it('has no a11y violations in chart state', async () => {
    const { container } = render(
      <AccessibleTableToggle chartNode={<Chart />} tableNode={<TableView />} />
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
```

## Out of scope

- Do NOT manage the data for the table node — callers provide pre-built nodes
- Do NOT animate the transition
- Do NOT persist toggle state to localStorage
