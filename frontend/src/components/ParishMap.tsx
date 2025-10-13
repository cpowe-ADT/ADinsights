import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer } from "react-leaflet";
import type { Feature, FeatureCollection } from "geojson";
import L from "leaflet";
import { Link } from "react-router-dom";

import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";
import styles from "./ParishMap.module.css";

const COLOR_RAMP = ["#dbeafe", "#bfdbfe", "#60a5fa", "#2563eb", "#1d4ed8"] as const;

interface ParishMapProps {
  height?: number;
}

const JAMAICA_CENTER: [number, number] = [18.1096, -77.2975];

function getFeatureName(feature: Feature): string {
  const name =
    typeof feature?.properties === "object" && feature.properties !== null
      ? (feature.properties as { name?: unknown }).name
      : undefined;

  return typeof name === "string" && name.length > 0 ? name : "Unknown";
}

function computeBreaks(values: number[]): number[] {
  if (values.length === 0) {
    return [0, 0, 0, 0];
  }
  const sorted = [...values].sort((a, b) => a - b);
  const quantile = (p: number) => {
    const idx = Math.floor(p * (sorted.length - 1));
    return sorted[idx];
  };
  return [quantile(0.25), quantile(0.5), quantile(0.75), quantile(0.9)];
}

function getColor(value: number, breaks: number[]): string {
  if (value <= breaks[0]) return COLOR_RAMP[0];
  if (value <= breaks[1]) return COLOR_RAMP[1];
  if (value <= breaks[2]) return COLOR_RAMP[2];
  if (value <= breaks[3]) return COLOR_RAMP[3];
  return COLOR_RAMP[4];
}

const ParishMap = ({ height = 320 }: ParishMapProps) => {
  const { parishData, parishStatus, parishError, selectedMetric, selectedParish, setSelectedParish } =
    useDashboardStore((state) => ({
      parishData: state.parish.data ?? [],
      parishStatus: state.parish.status,
      parishError: state.parish.error,
      selectedMetric: state.selectedMetric,
      selectedParish: state.selectedParish,
      setSelectedParish: state.setSelectedParish,
    }));
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const geoJsonRef = useRef<L.GeoJSON | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: "#1e293b",
    weight: 1,
    fillColor: COLOR_RAMP[0],
    fillOpacity: 0.8,
  }));
  const [scrollZoomEnabled, setScrollZoomEnabled] = useState(false);

  useEffect(() => {
    fetch("/jm_parishes.json")
      .then((res) => res.json())
      .then((data: FeatureCollection) => setGeojson(data))
      .catch((error) => console.error("Failed to load GeoJSON", error));
  }, []);

  const metricByParish = useMemo(() => {
    return parishData.reduce<Record<string, number>>((acc, row) => {
      const key = row.parish;
      const value = Number(row[selectedMetric as keyof typeof row] ?? 0);
      acc[key] = value;
      return acc;
    }, {});
  }, [parishData, selectedMetric]);

  const metricValues = useMemo(() => Object.values(metricByParish), [metricByParish]);
  const breaks = useMemo(() => computeBreaks(metricValues), [metricValues]);
  const currency = useMemo(() => parishData[0]?.currency ?? "USD", [parishData]);

  const formatMetricValue = useCallback(
    (value: number) => {
      if (selectedMetric === "spend") {
        return formatCurrency(value, currency);
      }
      if (selectedMetric === "roas") {
        return formatRatio(value, 2);
      }
      return formatNumber(value);
    },
    [currency, selectedMetric]
  );

  const metricLabel = useMemo(() => {
    const labels: Record<string, string> = {
      spend: "Spend",
      impressions: "Impressions",
      clicks: "Clicks",
      conversions: "Conversions",
      roas: "ROAS",
    };
    return labels[selectedMetric] ?? selectedMetric.toUpperCase();
  }, [selectedMetric]);

  const legendSteps = useMemo(() => {
    const [q1, q2, q3, q4] = breaks;
    const minValue = metricValues.length > 0 ? Math.min(...metricValues) : 0;

    const formatRange = (low: number, high: number, mode: "first" | "middle" | "last") => {
      if (mode === "first") {
        return `≤ ${formatMetricValue(high)}`;
      }
      if (mode === "last") {
        return `> ${formatMetricValue(high)}`;
      }
      if (low === high) {
        return formatMetricValue(high);
      }
      return `${formatMetricValue(low)} – ${formatMetricValue(high)}`;
    };

    return [
      { color: COLOR_RAMP[0], label: formatRange(minValue, q1, "first") },
      { color: COLOR_RAMP[1], label: formatRange(q1, q2, "middle") },
      { color: COLOR_RAMP[2], label: formatRange(q2, q3, "middle") },
      { color: COLOR_RAMP[3], label: formatRange(q3, q4, "middle") },
      { color: COLOR_RAMP[4], label: formatRange(q4, q4, "last") },
    ];
  }, [breaks, formatMetricValue, metricValues]);

  const styleForParish = useCallback(
    (name: string): L.PathOptions => {
      const value = metricByParish[name] ?? 0;

      return {
        fillColor: getColor(value, breaks),
        weight: selectedParish === name ? 2 : 1,
        color: selectedParish === name ? "#f97316" : "#1e293b",
        fillOpacity: 0.8,
      };
    },
    [breaks, metricByParish, selectedParish]
  );

  const tooltipForParish = useCallback(
    (name: string) => {
      const value = metricByParish[name] ?? 0;
      const formattedValue = formatMetricValue(value);

      return `
        <div class="${styles.tooltipInner}">
          <span class="${styles.tooltipName}">${name}</span>
          <span class="${styles.tooltipMetric}">${metricLabel}: ${formattedValue}</span>
        </div>
      `.trim();
    },
    [formatMetricValue, metricByParish, metricLabel]
  );

  useEffect(() => {
    styleForParishRef.current = styleForParish;
  }, [styleForParish]);

  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      const name = getFeatureName(feature);

      const pathLayer = layer as L.Path;
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name));
      }

      const tooltipText = tooltipForParish(name);
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined };
      const existingTooltip = typedLayer.getTooltip?.();
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText);
      } else {
        typedLayer.bindTooltip(tooltipText, {
          sticky: true,
          direction: "top",
          className: styles.tooltip,
          offset: L.point(0, -8),
          opacity: 1,
        });
      }

      layer.on({
        click: () => setSelectedParish(name),
        mouseover: () => {
          pathLayer.setStyle({ weight: Math.max(pathLayer.options.weight ?? 1, 2) });
        },
        mouseout: () => {
          pathLayer.setStyle(styleForParishRef.current(name));
        },
      });
    },
    [setSelectedParish, styleForParish, tooltipForParish]
  );

  useEffect(() => {
    if (!geoJsonRef.current) {
      return;
    }

    geoJsonRef.current.eachLayer((layer) => {
      const feature = (layer as L.Layer & { feature?: Feature }).feature;
      if (!feature) {
        return;
      }

      const name = getFeatureName(feature);
      const pathLayer = layer as L.Path;
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name));
      }

      const tooltipText = tooltipForParish(name);
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined };
      const existingTooltip = typedLayer.getTooltip?.();
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText);
      } else {
        typedLayer.bindTooltip(tooltipText, {
          sticky: true,
          direction: "top",
          className: styles.tooltip,
          offset: L.point(0, -8),
          opacity: 1,
        });
      }
    });
  }, [styleForParish, tooltipForParish]);

  const mapRefCallback = useCallback((map: L.Map | null) => {
    if (!map) {
      return;
    }

    mapRef.current = map;
    map.scrollWheelZoom.disable();
  }, []);

  const toggleScrollZoom = useCallback(() => {
    if (!mapRef.current) {
      return;
    }

    if (scrollZoomEnabled) {
      mapRef.current.scrollWheelZoom.disable();
    } else {
      mapRef.current.scrollWheelZoom.enable();
    }
    setScrollZoomEnabled((state) => !state);
  }, [scrollZoomEnabled]);

  if (parishStatus === "loading") {
    return <div className="status-message muted">Preparing the parish heatmap…</div>;
  }

  if (parishStatus === "error") {
    return <div className="status-message error">{parishError ?? "Unable to render the parish map."}</div>;
  }

  if (parishData.length === 0) {
    return <div className="status-message muted">Map insights will appear once this tenant has campaign data.</div>;
  }

  return (
    <div className={styles.mapShell} style={{ height }}>
      <div className={styles.overlay}>
        <Link to="/dashboards/map" className={styles.fullMapLink}>
          View full map
        </Link>
        <button
          type="button"
          className={styles.toggleButton}
          onClick={toggleScrollZoom}
          aria-pressed={scrollZoomEnabled}
          aria-label={scrollZoomEnabled ? "Disable scroll zoom" : "Enable scroll zoom"}
        >
          <span aria-hidden="true" className={styles.toggleIcon}>
            <svg viewBox="0 0 24 24" role="img" focusable="false">
              <path
                d="M12 3a3 3 0 0 0-3 3v4.382a3 3 0 0 0-.879 2.12v5.5A2.998 2.998 0 0 0 10.5 21h3a2.998 2.998 0 0 0 2.379-1.498 2.998 2.998 0 0 0 .121-2.502v-5.498A3 3 0 0 0 15 10.382V6a3 3 0 0 0-3-3Zm-1.5 3a1.5 1.5 0 1 1 3 0v4.618a1.5 1.5 0 0 1-.439 1.061l-.061.06v.261h-2v-.26l-.061-.062A1.5 1.5 0 0 1 10.5 10.618Z"
              />
              {!scrollZoomEnabled ? (
                <line x1="5" y1="19" x2="19" y2="5" />
              ) : null}
            </svg>
          </span>
        </button>
      </div>
      <div className={styles.legend} role="group" aria-label={`${metricLabel} legend`}>
        <span className={styles.legendTitle}>{metricLabel}</span>
        <ul>
          {legendSteps.map((step) => (
            <li key={`${step.color}-${step.label}`}>
              <span className={styles.legendSwatch} style={{ backgroundColor: step.color }} aria-hidden="true" />
              <span className={styles.legendLabel}>{step.label}</span>
            </li>
          ))}
        </ul>
      </div>
      <MapContainer
        ref={mapRefCallback}
        center={JAMAICA_CENTER}
        zoom={7}
        scrollWheelZoom={scrollZoomEnabled}
        className={styles.map}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geojson ? (
          <GeoJSONLayer
            ref={geoJsonRef}
            data={geojson as FeatureCollection}
            onEachFeature={onEachFeature}
          />
        ) : null}
      </MapContainer>
    </div>
  );
};

export default ParishMap;
