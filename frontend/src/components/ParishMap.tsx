// @ts-nocheck

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Feature, FeatureCollection } from "geojson";
import L from "leaflet";
import { Link } from "react-router-dom";

import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import Skeleton from "./Skeleton";
import { useTheme } from "./ThemeProvider";
import styles from "./ParishMap.module.css";

const COLOR_RAMP = ["#dbeafe", "#bfdbfe", "#60a5fa", "#2563eb", "#1d4ed8"] as const;
const FALLBACK_LIGHT_PALETTE = ["#f1f5f9", "#bfdbfe", "#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8"] as const;
const FALLBACK_DARK_PALETTE = ["#0f172a", "#1e3a8a", "#1d4ed8", "#2563eb", "#38bdf8", "#93c5fd"] as const;
const JAMAICA_CENTER: [number, number] = [18.1096, -77.2975];

interface ParishMapProps {
  height?: number;
  onRetry?: () => void;
}

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

function resolveCssColor(variableName: string, fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }

  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(variableName)
    .trim();
  return value.length > 0 ? value : fallback;
}

function getColor(value: number, breaks: number[], palette: readonly string[]): string {
  if (value === 0) return palette[0];
  if (value <= breaks[0]) return palette[1];
  if (value <= breaks[1]) return palette[2];
  if (value <= breaks[2]) return palette[3];
  if (value <= breaks[3]) return palette[4];
  return palette[5];
}

const MapPlaceholderIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.4">
    <path d="M16 14 8 18v18l8-4 10 4 12-6V10l-12 6-10-2Z" strokeLinejoin="round" />
    <circle cx="32" cy="16" r="3.5" fill="currentColor" stroke="none" />
  </svg>
);

const ParishMap = ({ height = 320, onRetry }: ParishMapProps) => {
  const { theme } = useTheme();
  const {
    parishData,
    parishStatus,
    parishError,
    selectedMetric,
    selectedParish,
    setSelectedParish,
  } = useDashboardStore((state) => ({
    parishData: state.parish.data ?? [],
    parishStatus: state.parish.status,
    parishError: state.parish.error,
    selectedMetric: state.selectedMetric,
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
  }));
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: "#1e293b",
    weight: 1,
    fillColor: COLOR_RAMP[0],
    fillOpacity: 0.8,
  }));
  const [scrollZoomEnabled, setScrollZoomEnabled] = useState(false);

  const fallbackPalette = theme === "dark" ? FALLBACK_DARK_PALETTE : FALLBACK_LIGHT_PALETTE;
  const mapPalette = useMemo<readonly string[]>(() => {
    return fallbackPalette.map((color, index) => resolveCssColor(`--map-fill-${index}`, color));
  }, [fallbackPalette]);

  const borderColor = useMemo(
    () => resolveCssColor("--map-border", theme === "dark" ? "rgba(226, 232, 240, 0.75)" : "#1e293b"),
    [theme],
  );
  const highlightColor = useMemo(
    () => resolveCssColor("--map-highlight", theme === "dark" ? "#fbbf24" : "#f97316"),
    [theme],
  );

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
    [currency, selectedMetric],
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
        fillColor: getColor(value, breaks, mapPalette),
        weight: selectedParish === name ? 2 : 1,
        color: selectedParish === name ? highlightColor : borderColor,
        fillOpacity: 0.8,
      };
    },
    [borderColor, breaks, highlightColor, mapPalette, metricByParish, selectedParish],
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
    [formatMetricValue, metricByParish, metricLabel],
  );

  useEffect(() => {
    styleForParishRef.current = styleForParish;
  }, [styleForParish]);

  const tileLayerUrl = useMemo(
    () =>
      theme === "dark"
        ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    [theme],
  );
  const tileAttribution = useMemo(
    () =>
      theme === "dark"
        ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    [theme],
  );

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
    [setSelectedParish, styleForParish, tooltipForParish],
  );

  useEffect(() => {
    if (!mapRef.current || !mapNodeRef.current || mapRef.current._container !== mapNodeRef.current) {
      const node = mapNodeRef.current;
      if (!node) {
        return;
      }

      const map = L.map(node, {
        center: JAMAICA_CENTER,
        zoom: 7,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
        boxZoom: false,
        keyboard: false,
        zoomControl: false,
      });

      mapRef.current = map;
      requestAnimationFrame(() => {
        map.invalidateSize();
      });
    } else {
      requestAnimationFrame(() => {
        mapRef.current?.invalidateSize();
      });
    }

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        tileLayerRef.current = null;
        geoJsonLayerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current) {
      return;
    }

    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }

    const layer = L.tileLayer(tileLayerUrl, { attribution: tileAttribution });
    layer.addTo(mapRef.current);
    tileLayerRef.current = layer;
  }, [tileAttribution, tileLayerUrl]);

  useEffect(() => {
    if (!mapRef.current || !geojson) {
      return;
    }

    if (geoJsonLayerRef.current) {
      geoJsonLayerRef.current.remove();
    }

    const layer = L.geoJSON(geojson as FeatureCollection, {
      onEachFeature,
    });

    geoJsonLayerRef.current = layer;
    layer.addTo(mapRef.current);
  }, [geojson, onEachFeature]);

  useEffect(() => {
    if (!geoJsonLayerRef.current) {
      return;
    }

    geoJsonLayerRef.current.eachLayer((layer) => {
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

  useEffect(() => {
    if (!mapRef.current) {
      return;
    }

    requestAnimationFrame(() => {
      mapRef.current?.invalidateSize();
    });
  }, [height, geojson]);

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

  if (parishStatus === "loading" && parishData.length === 0) {
    return (
      <div className="widget-skeleton" aria-busy="true">
        <Skeleton height="300px" borderRadius="1rem" />
      </div>
    );
  }

  if (parishStatus === "loading") {
    return <div className="status-message muted">Preparing the parish heatmap…</div>;
  }

  if (parishStatus === "error" && parishData.length === 0) {
    return (
      <ErrorState
        message={parishError ?? "Unable to render the parish map."}
        onRetry={onRetry}
        retryLabel="Retry load"
      />
    );
  }

  if (parishData.length === 0) {
    return (
      <EmptyState
        icon={<MapPlaceholderIcon />}
        title="No map insights yet"
        message="Map insights will appear once this tenant has campaign data."
        actionLabel="Refresh data"
        onAction={() => onRetry?.()}
        actionVariant="secondary"
      />
    );
  }

  return (
    <div className={styles.mapShell} style={{ height }}>
      <div ref={mapNodeRef} className={`leaflet-container ${styles.map}`} />

      <div className={styles.overlay}>
        <Link to="/dashboards/map" className={styles.fullMapLink}>
          Open full map
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
              {!scrollZoomEnabled ? <line x1="5" y1="19" x2="19" y2="5" /> : null}
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
    </div>
  );
};

export default ParishMap;
