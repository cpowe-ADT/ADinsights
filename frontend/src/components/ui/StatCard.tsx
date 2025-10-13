import { useMemo } from "react";

import Card from "./Card";

export interface StatCardProps {
  label: string;
  value: string | number;
  sparkline?: number[];
}

const clampSparkline = (values?: number[]) => {
  if (!values) {
    return [];
  }

  return values.filter((point) => Number.isFinite(point));
};

const StatCard = ({ label, value, sparkline }: StatCardProps) => {
  const sanitizedValues = useMemo(() => clampSparkline(sparkline), [sparkline]);

  const paths = useMemo(() => {
    if (sanitizedValues.length < 2) {
      return undefined;
    }

    const min = Math.min(...sanitizedValues);
    const max = Math.max(...sanitizedValues);
    const range = max - min || 1;

    const points = sanitizedValues.map((point, index) => {
      const x = (index / (sanitizedValues.length - 1)) * 100;
      const y = 32 - ((point - min) / range) * 28 - 2;

      return { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) };
    });

    const linePath = points
      .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
      .join(" ");

    const areaPath = `${linePath} L100,32 L0,32 Z`;

    return { linePath, areaPath };
  }, [sanitizedValues]);

  return (
    <Card title={label} className="statCard">
      <div className="statCardBody">
        <span className="statCardValue">{value}</span>
        {paths ? (
          <div className="statCardSparkline" role="img" aria-label={`${label} trend`}>
            <svg viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
              <path className="statCardSparklineArea" d={paths.areaPath} />
              <path className="statCardSparklineLine" d={paths.linePath} />
            </svg>
          </div>
        ) : null}
      </div>
    </Card>
  );
};

export default StatCard;
