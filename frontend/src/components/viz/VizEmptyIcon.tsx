/**
 * Shared no-data icon for viz primitive empty states. Thin SVG so we
 * do not depend on an external icon library and we keep the kit
 * self-contained. S1b's `viz/EmptyState.tsx` wrapper may swap this out
 * for a reason-code-specific icon.
 */
const VizEmptyIcon = () => (
  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
    <path
      d="M3 3v18h18"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M7 14l3-3 3 3 4-5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray="2 2"
    />
  </svg>
);

export default VizEmptyIcon;
