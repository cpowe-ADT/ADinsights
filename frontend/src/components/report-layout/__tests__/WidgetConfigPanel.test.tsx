import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import WidgetConfigPanel from '../WidgetConfigPanel';
import type { DashboardWidget } from '../layoutSchema';

const widget: DashboardWidget = {
  id: 'a',
  type: 'kpi',
  title: 'Spend',
  x: 1,
  y: 1,
  w: 3,
  h: 2,
  dataKey: 'summary.totalSpend',
  options: { format: 'currency', currency: 'JMD' },
};

describe('WidgetConfigPanel', () => {
  it('emits a title patch', () => {
    const onChange = vi.fn();
    render(<WidgetConfigPanel widget={widget} onChange={onChange} onClose={() => {}} />);
    fireEvent.change(screen.getByDisplayValue('Spend'), { target: { value: 'Total spend' } });
    expect(onChange).toHaveBeenCalledWith({ title: 'Total spend' });
  });

  it('emits a dataKey patch (binding to live data)', () => {
    const onChange = vi.fn();
    render(<WidgetConfigPanel widget={widget} onChange={onChange} onClose={() => {}} />);
    fireEvent.change(screen.getByDisplayValue('summary.totalSpend'), {
      target: { value: 'summary.totalClicks' },
    });
    expect(onChange).toHaveBeenCalledWith({ dataKey: 'summary.totalClicks' });
  });

  it('merges option changes (currency) without dropping other options', () => {
    const onChange = vi.fn();
    render(<WidgetConfigPanel widget={widget} onChange={onChange} onClose={() => {}} />);
    fireEvent.change(screen.getByDisplayValue('JMD'), { target: { value: 'USD' } });
    expect(onChange).toHaveBeenCalledWith({ options: { format: 'currency', currency: 'USD' } });
  });

  it('calls onClose', () => {
    const onClose = vi.fn();
    render(<WidgetConfigPanel widget={widget} onChange={() => {}} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText('Close settings'));
    expect(onClose).toHaveBeenCalled();
  });
});
