import type { CSSProperties } from 'react';

interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  borderRadius?: number | string;
  className?: string;
  style?: CSSProperties;
}

function toCssValue(value?: number | string): string | undefined {
  if (typeof value === 'number') {
    return `${value}px`;
  }
  return value;
}

const Skeleton = ({
  width = '100%',
  height = '1rem',
  borderRadius = '0.75rem',
  className,
  style,
}: SkeletonProps) => {
  const resolvedStyle: CSSProperties = {
    width: toCssValue(width),
    height: toCssValue(height),
    borderRadius: toCssValue(borderRadius),
    ...style,
  };

  const classes = ['skeleton', className].filter(Boolean).join(' ');

  return <div className={classes} style={resolvedStyle} aria-hidden="true" role="presentation" />;
};

export default Skeleton;
