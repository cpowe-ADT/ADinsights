import { useEffect } from "react";
import ParishMap from "./components/ParishMap";
import MetricsGrid from "./components/MetricsGrid";
import useDashboardStore, { MetricKey } from "./state/useDashboardStore";

const metricOptions: { label: string; value: MetricKey }[] = [
  { label: "Impressions", value: "impressions" },
  { label: "Clicks", value: "clicks" },
  { label: "Spend", value: "spend" },
  { label: "Conversions", value: "conversions" },
  { label: "ROAS", value: "roas" }
];

function App() {
  const { loadSampleData, selectedMetric, setSelectedMetric } = useDashboardStore();

  useEffect(() => {
    loadSampleData().catch((error) => {
      console.error("Failed to load sample data", error);
    });
  }, [loadSampleData]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Jamaica Ads Performance</h1>
          <p>Mock data to validate the multi-tenant dashboard experience.</p>
        </div>
        <div>
          <label htmlFor="metric-select">Metric: </label>
          <select
            id="metric-select"
            value={selectedMetric}
            onChange={(event) => setSelectedMetric(event.target.value as MetricKey)}
          >
            {metricOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </header>
      <div className="app-content">
        <section className="map-pane">
          <ParishMap />
        </section>
        <section className="grid-pane">
          <MetricsGrid />
        </section>
      </div>
    </div>
  );
}
import { useEffect, useMemo, useState } from "react";
import { ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import DeckGL from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import type { Feature, FeatureCollection } from "geojson";
import type { LeafletMouseEvent } from "leaflet";
import "leaflet/dist/leaflet.css";
import styles from "./styles/App.module.css";

type CampaignRow = {
  id: string;
  campaign: string;
  creative: string;
  spend: number;
  budget: number;
  impressions: number;
};

const campaignData: CampaignRow[] = [
  {
    id: "1",
    campaign: "Awareness - North",
    creative: "Video",
    spend: 1200,
    budget: 2000,
    impressions: 50000
  },
  {
    id: "2",
    campaign: "Conversions - East",
    creative: "Static",
    spend: 850,
    budget: 1500,
    impressions: 32000
  },
  {
    id: "3",
    campaign: "Remarketing - South",
    creative: "Carousel",
    spend: 600,
    budget: 1000,
    impressions: 22000
  }
];

const parishFeatures: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { parish: "Orleans", spend: 1200 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-90.14, 30.02],
            [-89.9, 30.02],
            [-89.9, 29.85],
            [-90.14, 29.85],
            [-90.14, 30.02]
          ]
        ]
      }
    },
    {
      type: "Feature",
      properties: { parish: "Jefferson", spend: 850 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-90.3, 29.9],
            [-90.0, 29.9],
            [-90.0, 29.6],
            [-90.3, 29.6],
            [-90.3, 29.9]
          ]
        ]
      }
    }
  ]
};

const DeckChoropleth = ({ data }: { data: FeatureCollection }) => {
  const layer = useMemo(
    () =>
      new GeoJsonLayer({
        id: "parish-layer",
        data,
        stroked: true,
        filled: true,
        getLineWidth: 20,
        lineWidthUnits: "meters",
        getLineColor: [32, 64, 128, 255],
        getFillColor: (feature: Feature) => {
          const spend = (feature.properties as { spend: number }).spend;
          const intensity = Math.min(255, Math.round((spend / 2000) * 255));
          return [255, 140 - intensity / 2, 0 + intensity / 4, 180];
        }
      }),
    [data]
  );

  return (
    <DeckGL
      layers={[layer]}
      initialViewState={{
        longitude: -90.07,
        latitude: 29.95,
        zoom: 9,
        pitch: 0
      }}
      controller
    />
  );
};

type ParishOverlayProps = {
  data: FeatureCollection;
  onSelect?: (parish: string) => void;
};

type GeoJSONClickEvent = LeafletMouseEvent & { layer?: { feature?: Feature } };

function ParishOverlay({ data, onSelect }: ParishOverlayProps) {
  return (
    <GeoJSON
      data={data}
      eventHandlers={{
        click: (event: GeoJSONClickEvent) => {
          const parish = event.layer?.feature?.properties?.parish;
          if (parish && onSelect) {
            onSelect(String(parish));
          }
        }
      }}
      style={(feature?: Feature) => {
        const spend = feature?.properties?.spend ?? 0;
        const intensity = Math.min(1, spend / 2000);
        return {
          color: "#1f2933",
          weight: 1,
          fillColor: `rgba(${255}, ${150 - intensity * 80}, ${90}, 0.4)`,
          fillOpacity: 0.6
        };
      }}
    />
  );
}

const DashboardTable = ({ data }: { data: CampaignRow[] }) => {
  const columns = useMemo<ColumnDef<CampaignRow>[]>(
    () => [
      {
        accessorKey: "campaign",
        header: "Campaign"
      },
      {
        accessorKey: "creative",
        header: "Creative"
      },
      {
        accessorKey: "spend",
        header: "Spend",
        cell: (info) => {
          const value = Number(info.getValue() ?? 0);
          return `$${value.toLocaleString()}`;
        }
      },
      {
        accessorKey: "budget",
        header: "Budget",
        cell: (info) => {
          const value = Number(info.getValue() ?? 0);
          return `$${value.toLocaleString()}`;
        }
      },
      {
        accessorKey: "impressions",
        header: "Impressions",
        cell: (info) => {
          const value = Number(info.getValue() ?? 0);
          return value.toLocaleString();
        }
      }
    ],
    []
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  return (
    <table className={styles.table}>
      <thead>
        {table.getHeaderGroups().map((headerGroup) => (
          <tr key={headerGroup.id}>
            {headerGroup.headers.map((header) => (
              <th key={header.id}>
                {header.isPlaceholder
                  ? null
                  : flexRender(header.column.columnDef.header, header.getContext())}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <td key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
};

const App = () => {
  const [selectedParish, setSelectedParish] = useState<string | null>(null);
  const [summary, setSummary] = useState<string>(
    "Select a parish or campaign row to generate an AI summary."
  );
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

  useEffect(() => {
    if (!selectedParish) {
      setSummary("Select a parish or campaign row to generate an AI summary.");
      return;
    }

    const controller = new AbortController();
    const run = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/insights/summary`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            context: "parish",
            parish: selectedParish,
            spend: parishFeatures.features.find(
              (feature) => feature.properties?.parish === selectedParish
            )?.properties?.spend,
          }),
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Unexpected status ${response.status}`);
        }
        const { summary: aiSummary } = await response.json();
        setSummary(aiSummary);
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setSummary(
            "AI summary unavailable. Review campaign dashboards for more detail."
          );
        }
      }
    };

    run();
    return () => controller.abort();
  }, [API_BASE_URL, selectedParish]);

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <h1>ADinsights Campaign Intelligence</h1>
        <p>
          Monitor campaign pacing, creative effectiveness, and parish level reach
          with a unified workspace.
        </p>
      </header>
      <main className={styles.main}>
        <section className={styles.tablePanel}>
          <h2>Campaign Pacing</h2>
          <DashboardTable data={campaignData} />
        </section>
        <section className={styles.mapPanel}>
          <h2>Parish Reach Choropleth</h2>
          <div className={styles.mapContainer}>
            <MapContainer center={[29.95, -90.07]} zoom={9} scrollWheelZoom>
              <TileLayer
                attribution='&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <ParishOverlay data={parishFeatures} onSelect={setSelectedParish} />
            </MapContainer>
            <div className={styles.deckOverlay}>
              <DeckChoropleth data={parishFeatures} />
            </div>
          </div>
          <div className={styles.legend}>
            <span>Budget Utilization</span>
            <div className={styles.gradientBar} />
          </div>
        </section>
      </main>
      <aside className={styles.sidebar}>
        <h2>Parish Spotlight</h2>
        <p className={styles.spotlightLabel}>{selectedParish ?? "Parish"}</p>
        <p>{summary}</p>
        <p className={styles.helperText}>
          Deck.gl overlay demonstrates how high-spend parishes become more
          saturated to highlight budget pacing concerns.
        </p>
      </aside>
    </div>
  );
};

export default App;
