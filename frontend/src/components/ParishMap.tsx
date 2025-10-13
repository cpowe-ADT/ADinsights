import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer } from "react-leaflet";
import type { Feature, FeatureCollection } from "geojson";
import L from "leaflet";

import useDashboardStore from "../state/useDashboardStore";
import { formatCurrency, formatNumber, formatRatio } from "../lib/format";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import Skeleton from "./Skeleton";

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
  if (value === 0) return "#f1f5f9";
  if (value <= breaks[0]) return "#bfdbfe";
  if (value <= breaks[1]) return "#60a5fa";
  if (value <= breaks[2]) return "#3b82f6";
  if (value <= breaks[3]) return "#2563eb";
  return "#1d4ed8";
}

interface ParishMapProps {
  onRetry?: () => void;
}

const MapPlaceholderIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.4">
    <path d="M16 14 8 18v18l8-4 10 4 12-6V10l-12 6-10-2Z" strokeLinejoin="round" />
    <circle cx="32" cy="16" r="3.5" fill="currentColor" stroke="none" />
  </svg>
);

const ParishMap = ({ onRetry }: ParishMapProps) => {
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
  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: "#1e293b",
    weight: 1,
    fillColor: "#f1f5f9",
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

  if (parishStatus === "loading" && parishData.length === 0) {
    return (
      <div className="widget-skeleton" aria-busy="true">
        <Skeleton height="300px" borderRadius="1rem" />
      </div>
    );
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
    <MapContainer center={JAMAICA_CENTER} zoom={7} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
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
  );
};

export default ParishMap;
