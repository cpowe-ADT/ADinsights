import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import Breadcrumbs from '../Breadcrumbs';

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

describe('Breadcrumbs', () => {
  it('renders breadcrumb navigation with correct aria label', () => {
    renderWithRouter(<Breadcrumbs items={[{ label: 'Home', to: '/' }]} />);
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
  });

  it('renders all breadcrumb items', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Dashboards', to: '/dashboards' },
      { label: 'Overview' },
    ];
    renderWithRouter(<Breadcrumbs items={items} />);
    // Items appear in both the ol and the dropdown select, so use getAllByText
    expect(screen.getAllByText('Home').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Dashboards').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Overview').length).toBeGreaterThanOrEqual(1);
  });

  it('renders intermediate items as links', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Dashboards', to: '/dashboards' },
      { label: 'Overview' },
    ];
    renderWithRouter(<Breadcrumbs items={items} />);
    const homeLink = screen.getByRole('link', { name: 'Home' });
    expect(homeLink).toHaveAttribute('href', '/');
    const dashLink = screen.getByRole('link', { name: 'Dashboards' });
    expect(dashLink).toHaveAttribute('href', '/dashboards');
  });

  it('renders the last item as a span with aria-current="page"', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Current Page' },
    ];
    renderWithRouter(<Breadcrumbs items={items} />);
    // The span in the ol list (not the option in the dropdown)
    const matches = screen.getAllByText('Current Page');
    const spanMatch = matches.find((el) => el.tagName === 'SPAN' && el.getAttribute('aria-current') === 'page');
    expect(spanMatch).toBeDefined();
  });

  it('does not render the last item as a link even if it has a "to" prop', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Current', to: '/current' },
    ];
    renderWithRouter(<Breadcrumbs items={items} />);
    const matches = screen.getAllByText('Current');
    const spanMatch = matches.find((el) => el.tagName === 'SPAN' && el.getAttribute('aria-current') === 'page');
    expect(spanMatch).toBeDefined();
  });

  it('renders separator between items but not after the last', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Dashboards', to: '/dashboards' },
      { label: 'Overview' },
    ];
    const { container } = renderWithRouter(<Breadcrumbs items={items} />);
    const separators = container.querySelectorAll('li span');
    // Each li has at most a separator span; count the "/" text nodes
    const slashSpans = Array.from(separators).filter((el) => el.textContent === '/');
    expect(slashSpans).toHaveLength(2);
  });

  it('renders the mobile dropdown select', () => {
    const items = [
      { label: 'Home', to: '/' },
      { label: 'Overview' },
    ];
    renderWithRouter(<Breadcrumbs items={items} />);
    expect(screen.getByLabelText('Navigate to')).toBeInTheDocument();
  });

  it('handles a single breadcrumb item', () => {
    renderWithRouter(<Breadcrumbs items={[{ label: 'Home' }]} />);
    const matches = screen.getAllByText('Home');
    const spanMatch = matches.find((el) => el.tagName === 'SPAN' && el.getAttribute('aria-current') === 'page');
    expect(spanMatch).toBeDefined();
  });
});
