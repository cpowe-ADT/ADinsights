import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';

import LayoutEditor from './LayoutEditor';
import { slbSampleLayout } from './sampleLayouts';
import type { DashboardLayoutConfig } from './layoutSchema';

const meta: Meta<typeof LayoutEditor> = {
  title: 'Report Layout/LayoutEditor',
  component: LayoutEditor,
  parameters: { layout: 'fullscreen' },
};

export default meta;

type Story = StoryObj<typeof LayoutEditor>;

/** The editor is controlled, so the story owns the layout state. */
const Editable = () => {
  const [layout, setLayout] = useState<DashboardLayoutConfig>(slbSampleLayout);
  return <LayoutEditor layout={layout} onChange={setLayout} onSave={() => undefined} />;
};

export const Interactive: Story = {
  render: () => <Editable />,
};
