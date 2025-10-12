import { useEffect, useMemo, useState } from "react";
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer } from "react-leaflet";
import type { Feature, FeatureCollection } from "geojson";
import L from "leaflet";

import useDashboardStore from "../state/useDashboardStore";

const JAMAICA_CENTER: [number, number] = [18.1096, -77.2975];

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

const ParishMap = () => {
  const { rows, selectedMetric, selectedParish, setSelectedParish } = useDashboardStore();
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    fetch("/jm_parishes.json")
      .then((res) => res.json())
      .then((data: FeatureCollection) => setGeojson(data))
      .catch((error) => console.error("Failed to load GeoJSON", error));
  }, []);

  const metricByParish = useMemo(() => {
    return rows.reduce<Record<string, number>>((acc, row) => {
      const key = row.parish;
      const value = row[selectedMetric];
      acc[key] = (acc[key] ?? 0) + value;
      return acc;
    }, {});
  }, [rows, selectedMetric]);

  const breaks = useMemo(() => computeBreaks(Object.values(metricByParish)), [metricByParish]);

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const name = feature.properties?.name ?? "Unknown";
    const value = metricByParish[name] ?? 0;

    if ((layer as L.Path).setStyle) {
      (layer as L.Path).setStyle({
        fillColor: getColor(value, breaks),
        weight: 1,
        color: selectedParish === name ? "#f97316" : "#1e293b",
        fillOpacity: 0.8,
      });
    }

    layer.on({
      click: () => setSelectedParish(name),
      mouseover: () => {
        (layer as L.Path).setStyle({ weight: 2 });
      },
      mouseout: () => {
        (layer as L.Path).setStyle({ weight: 1 });
      },
    });

    layer.bindTooltip(
      `${name}<br/>${selectedMetric.toUpperCase()}: ${value.toLocaleString()}`,
      { sticky: true }
    );
  };

  return (
    <MapContainer center={JAMAICA_CENTER} zoom={7} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {geojson ? (
        <GeoJSONLayer data={geojson as FeatureCollection} onEachFeature={onEachFeature} />
      ) : null}
    </MapContainer>
  );
};

export default ParishMap;
