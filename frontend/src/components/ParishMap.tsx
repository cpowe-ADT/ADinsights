import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer } from "react-leaflet";
import type { Feature, FeatureCollection } from "geojson";
import L from "leaflet";

import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";
import { useTheme } from "./ThemeProvider";

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

const FALLBACK_LIGHT_PALETTE = ["#f1f5f9", "#bfdbfe", "#60a5fa", "#3b82f6", "#2563eb", "#1d4ed8"] as const;
const FALLBACK_DARK_PALETTE = ["#0f172a", "#1e3a8a", "#1d4ed8", "#2563eb", "#38bdf8", "#93c5fd"] as const;

function resolveCssColor(variableName: string, fallback: string): string {
  if (typeof window === "undefined") {
    return fallback;
  }

  const value = getComputedStyle(document.documentElement).getPropertyValue(variableName).trim();
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

const ParishMap = () => {
  const { theme } = useTheme();
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

  const fallbackPalette = theme === "dark" ? FALLBACK_DARK_PALETTE : FALLBACK_LIGHT_PALETTE;
  const mapPalette = useMemo<readonly string[]>(() => {
    return fallbackPalette.map((color, index) =>
      resolveCssColor(`--map-fill-${index}`, color)
    );
  }, [fallbackPalette]);

  const borderColor = useMemo(
    () => resolveCssColor("--map-border", theme === "dark" ? "rgba(226, 232, 240, 0.75)" : "#1e293b"),
    [theme]
  );
  const highlightColor = useMemo(
    () => resolveCssColor("--map-highlight", theme === "dark" ? "#fbbf24" : "#f97316"),
    [theme]
  );

  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: borderColor,
    weight: 1,
    fillColor: mapPalette[0],
    fillOpacity: 0.8,
  }));

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

  const breaks = useMemo(() => computeBreaks(Object.values(metricByParish)), [metricByParish]);

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
    [borderColor, breaks, highlightColor, mapPalette, metricByParish, selectedParish]
  );

  const tooltipForParish = useCallback(
    (name: string) => {
      const value = metricByParish[name] ?? 0;
      const currency = parishData[0]?.currency ?? "USD";
      const labels: Record<string, string> = {
        spend: "Spend",
        impressions: "Impressions",
        clicks: "Clicks",
        conversions: "Conversions",
        roas: "ROAS",
      };

      const formattedValue =
        selectedMetric === "spend"
          ? formatCurrency(value, currency)
          : selectedMetric === "roas"
          ? formatRatio(value, 2)
          : formatNumber(value);

      const label = labels[selectedMetric] ?? selectedMetric.toUpperCase();
      return `${name}<br/>${label}: ${formattedValue}`;
    },
    [metricByParish, selectedMetric, parishData]
  );

  useEffect(() => {
    styleForParishRef.current = styleForParish;
  }, [styleForParish]);

  const tileLayerUrl =
    theme === "dark"
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const tileAttribution =
    theme === "dark"
      ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

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
        typedLayer.bindTooltip(tooltipText, { sticky: true });
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
        typedLayer.bindTooltip(tooltipText, { sticky: true });
      }
    });
  }, [styleForParish, tooltipForParish]);

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
    <MapContainer center={JAMAICA_CENTER} zoom={7} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
      <TileLayer attribution={tileAttribution} url={tileLayerUrl} />
      {geojson ? (
        <GeoJSONLayer
          ref={geoJsonRef}
          data={geojson as FeatureCollection}
          onEachFeature={onEachFeature}
        />
      ) : null}
    </MapContainer>
  );
};

export default ParishMap;
