# Finished Frontend Spec Review Checklist

Purpose: capture the senior frontend review for the finished product spec before sprint planning.
Use this as the template for Lina (Frontend Architect) and Joel (Design System).

## Review metadata

- Date:
- Reviewers:
- Outcome: Approved / Needs changes
- Summary:

## Coverage checks

- MVP, Post-MVP, Enterprise pages/routes all listed.
- Each page includes view, filters, drill paths, export/share, no-data, stale data.
- Global UI components are enumerated and match the design system scope.
- Key user actions cover auth, filtering, drill-through, sharing, and exports.
- Permissions/roles align with `docs/security/uac-spec.md`.
- API dependencies are complete and realistic for each maturity stage.
- Empty/error/loading states are defined with actionable CTAs.
- Analytics/telemetry events are listed for MVP/Post-MVP/Enterprise.
- Frontend acceptance checklist is present and testable.

## UX/IA checks (Lina)

- Navigation and routing align with the existing dashboard shell.
- Filter bar and snapshot freshness UX are consistent across dashboards.
- Drill-through flows are reversible and preserve context.
- Stale data messaging is unambiguous and timestamped.
- Mobile/responsive behavior is considered for each major view.
- Performance risks are called out for heavy tables/maps.

## Design system checks (Joel)

- Component reuse opportunities are identified (cards, tables, banners, modals).
- State variants (empty/error/stale/loading) are consistent and tokenized.
- Typography/spacing/visual hierarchy aligns with design system docs.
- Accessibility concerns (contrast, focus, keyboard flows) are flagged.
- Motion/visual language matches existing component standards.

## Dependencies & risks

- API endpoints exist or are tracked in backlog entries.
- Cross-stream dependencies are documented in backlog/task breakdown.
- Test coverage scope is defined for each new UI surface.
- Open questions are logged with owner + next action.

## Sign-off

- Lina (Frontend Architect): **\*\*\*\***\_\_\_\_**\*\*\*\*** Date: \***\*\_\_\*\***
- Joel (Design System): \***\*\*\*\*\***\_\_\_\_\***\*\*\*\*\*** Date: \***\*\_\_\*\***
