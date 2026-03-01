import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Feature, FeatureCollection } from 'geojson';
import L from 'leaflet';
import { Link } from 'react-router-dom';

import useDashboardStore, { type LoadStatus } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';
import { fetchParishGeometry } from '../lib/dataService';
import { MOCK_MODE } from '../lib/apiClient';
import DashboardState from './DashboardState';
import Skeleton from './Skeleton';
import { useTheme } from './ThemeProvider';
import styles from './ParishMap.module.css';
const JAMAICA_CENTER: [number, number] = [18.1096, -77.2975];

interface ParishMapProps {
  height?: number;
  onRetry?: () => void;
}

function withTenant(path: string, tenantId?: string): string {
  if (!tenantId) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}tenant_id=${encodeURIComponent(tenantId)}`;
}

const FEATURE_NAME_KEYS = [
  'name',
  'shapeName',
  'parish',
  'PARISH',
  'parishName',
  'PARISH_NAME',
  'NAME_2',
  'NAME_1',
  'NAME',
  'ADM2_EN',
  'ADM2NAME',
  'ADM2_NAME',
];

function resolveFeatureName(feature: Feature): string | undefined {
  if (typeof feature?.properties !== 'object' || feature.properties === null) {
    return undefined;
  }

  const properties = feature.properties as Record<string, unknown>;
  for (const key of FEATURE_NAME_KEYS) {
    const value = properties[key];
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) {
        return trimmed;
      }
    }
  }

  return undefined;
}

function getFeatureName(feature: Feature): string {
  return resolveFeatureName(feature) ?? 'Unknown';
}

function toDisplayParishName(value: string): string {
  return value.replace(/\bsaint\b/gi, 'St');
}

function normalizeParishName(value: string): string {
  return value
    .toLowerCase()
    .replace(/\./g, '')
    .replace(/\bsaint\b/g, 'st')
    .replace(/\s+/g, ' ')
    .trim();
}

function isFeatureCollection(value: unknown): value is FeatureCollection {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const collection = value as FeatureCollection;
  return collection.type === 'FeatureCollection' && Array.isArray(collection.features);
}

const resolvedEnv = typeof import.meta !== 'undefined' ? import.meta.env : undefined;
const MIN_PARISH_FEATURES = resolvedEnv?.MODE === 'test' || MOCK_MODE ? 1 : 10;

function isReasonableParishGeometry(collection: FeatureCollection): boolean {
  if (!Array.isArray(collection.features) || collection.features.length < MIN_PARISH_FEATURES) {
    return false;
  }

  let namedCount = 0;
  collection.features.forEach((feature) => {
    if (resolveFeatureName(feature)) {
      namedCount += 1;
    }
  });

  return namedCount >= MIN_PARISH_FEATURES;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case '&':
        return '&amp;';
      case '<':
        return '&lt;';
      case '>':
        return '&gt;';
      case '"':
        return '&quot;';
      case "'":
        return '&#39;';
      default:
        return char;
    }
  });
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

type MapPalette = {
  border: string;
  highlight: string;
  fills: [string, string, string, string, string, string];
};

const FALLBACK_PALETTE: MapPalette = {
  border: '#1f2937',
  highlight: '#0f172a',
  fills: ['#e2e8f0', '#bfdbfe', '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8'],
};

function resolvePalette(themeMode: string): MapPalette {
  void themeMode;
  if (typeof window === 'undefined') {
    return FALLBACK_PALETTE;
  }

  const styles = getComputedStyle(document.documentElement);
  const getVar = (name: string, fallback: string) => {
    const value = styles.getPropertyValue(name).trim();
    return value || fallback;
  };

  return {
    border: getVar('--map-border', FALLBACK_PALETTE.border),
    highlight: getVar('--map-highlight', FALLBACK_PALETTE.highlight),
    fills: [
      getVar('--map-fill-0', FALLBACK_PALETTE.fills[0]),
      getVar('--map-fill-1', FALLBACK_PALETTE.fills[1]),
      getVar('--map-fill-2', FALLBACK_PALETTE.fills[2]),
      getVar('--map-fill-3', FALLBACK_PALETTE.fills[3]),
      getVar('--map-fill-4', FALLBACK_PALETTE.fills[4]),
      getVar('--map-fill-5', FALLBACK_PALETTE.fills[5]),
    ],
  };
}

const MapPlaceholderIcon = () => (
  <svg
    width="48"
    height="48"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.4"
  >
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
    activeTenantId,
  } = useDashboardStore((state) => ({
    parishData: state.parish.data ?? [],
    parishStatus: state.parish.status,
    parishError: state.parish.error,
    selectedMetric: state.selectedMetric,
    selectedParish: state.selectedParish,
    setSelectedParish: state.setSelectedParish,
    activeTenantId: state.activeTenantId,
  }));
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null);
  const [geometryStatus, setGeometryStatus] = useState<LoadStatus>('idle');
  const [geometryError, setGeometryError] = useState<string>();
  const [mapReady, setMapReady] = useState(false);
  const [useSvgFallback, setUseSvgFallback] = useState(false);
  const geoJsonLayerRef = useRef<L.GeoJSON | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const mapNodeRef = useRef<HTMLDivElement | null>(null);
  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: 'var(--map-border)',
    weight: 1,
    fillColor: 'var(--map-fill-0)',
    fillOpacity: 0.8,
  }));
  const [scrollZoomEnabled, setScrollZoomEnabled] = useState(false);
  const geometryControllerRef = useRef<AbortController | null>(null);

  const palette = useMemo(() => resolvePalette(theme), [theme]);
  const borderColor = palette.border;
  const highlightColor = palette.highlight;

  const loadGeometry = useCallback((tenant?: string) => {
    geometryControllerRef.current?.abort();
    const controller = new AbortController();
    geometryControllerRef.current = controller;

    setGeometryStatus('loading');
    setGeometryError(undefined);

    const ensureGeometry = (data: FeatureCollection) => {
      if (!isFeatureCollection(data) || data.features.length === 0) {
        throw new Error('Parish geometry is unavailable.');
      }
      if (!isReasonableParishGeometry(data)) {
        throw new Error('Parish geometry is incomplete.');
      }
      return data;
    };

    const fetchFromPath = (path: string) =>
      fetchParishGeometry({
        path,
        mockPath: '/jm_parishes.json',
        signal: controller.signal,
      });

    const loadLocalFallback = async () => {
      const response = await fetch('/jm_parishes.json', { signal: controller.signal });
      if (!response.ok) {
        throw new Error('Fallback parish geometry load failed.');
      }
      return ensureGeometry((await response.json()) as FeatureCollection);
    };

    const resolveGeometry = async () => {
      const fallbackPaths = [
        withTenant('/analytics/parish-geometry/', tenant),
        withTenant('/dashboards/parish-geometry/', tenant),
      ];
      for (const path of fallbackPaths) {
        try {
          const data = await fetchFromPath(path);
          return ensureGeometry(data);
        } catch (error) {
          if (controller.signal.aborted) {
            throw error;
          }
        }
      }

      if (MOCK_MODE) {
        return loadLocalFallback();
      }

      try {
        return await loadLocalFallback();
      } catch (fallbackError) {
        console.warn('Fallback parish geometry load failed', fallbackError);
        throw fallbackError;
      }
    };

    resolveGeometry()
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        setGeojson(data);
        setUseSvgFallback(false);
        setGeometryStatus('loaded');
        geometryControllerRef.current = null;
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        console.error('Failed to load parish geometry', error);
        setGeometryStatus('error');
        setGeometryError(
          error instanceof Error ? error.message : 'Failed to load parish boundaries.',
        );
        setUseSvgFallback(true);
        geometryControllerRef.current = null;
      });
  }, []);

  useEffect(() => {
    loadGeometry(activeTenantId);
    return () => {
      if (geometryControllerRef.current) {
        geometryControllerRef.current.abort();
        geometryControllerRef.current = null;
      }
    };
  }, [activeTenantId, loadGeometry]);

  const metricByParish = useMemo(() => {
    return parishData.reduce<Record<string, number | null>>((acc, row) => {
      const raw = row.parish ?? 'Unknown';
      const key = normalizeParishName(raw);
      const rawValue = row[selectedMetric as keyof typeof row];
      if (rawValue === null || rawValue === undefined) {
        if (typeof acc[key] !== 'number') {
          acc[key] = null;
        }
        return acc;
      }
      const numeric = Number(rawValue);
      acc[key] = Number.isFinite(numeric) ? numeric : null;
      return acc;
    }, {});
  }, [parishData, selectedMetric]);

  const metricValues = useMemo(
    () =>
      Object.values(metricByParish).filter(
        (value): value is number => typeof value === 'number' && Number.isFinite(value),
      ),
    [metricByParish],
  );
  const breaks = useMemo(() => computeBreaks(metricValues), [metricValues]);
  const currency = useMemo(() => parishData[0]?.currency ?? 'USD', [parishData]);

  const formatMetricValue = useCallback(
    (value: number) => {
      if (selectedMetric === 'spend') {
        return formatCurrency(value, currency);
      }
      if (selectedMetric === 'roas') {
        return formatRatio(value, 2);
      }
      return formatNumber(value);
    },
    [currency, selectedMetric],
  );

  const metricLabel = useMemo(() => {
    const labels: Record<string, string> = {
      spend: 'Spend',
      impressions: 'Impressions',
      clicks: 'Clicks',
      conversions: 'Conversions',
      roas: 'ROAS',
    };
    return labels[selectedMetric] ?? selectedMetric.toUpperCase();
  }, [selectedMetric]);

  const legendSteps = useMemo(() => {
    if (metricValues.length === 0) {
      return [{ color: 'var(--map-fill-0)', label: 'No data' }];
    }

    const [q1, q2, q3, q4] = breaks;
    const minValue = Math.min(...metricValues);
    const maxValue = Math.max(...metricValues);

    const formatRange = (low: number, high: number, mode: 'first' | 'middle' | 'last') => {
      if (mode === 'first') {
        return `<= ${formatMetricValue(high)}`;
      }
      if (mode === 'last') {
        if (low === high) {
          return `>= ${formatMetricValue(high)}`;
        }
        return `>= ${formatMetricValue(low)}`;
      }
      if (low === high) {
        return formatMetricValue(high);
      }
      return `${formatMetricValue(low)} - ${formatMetricValue(high)}`;
    };

    if (minValue === maxValue) {
      return [
        { color: 'var(--map-fill-0)', label: 'No data' },
        { color: 'var(--map-fill-1)', label: formatMetricValue(minValue) },
      ];
    }

    return [
      { color: 'var(--map-fill-0)', label: 'No data' },
      { color: 'var(--map-fill-1)', label: formatRange(minValue, q1, 'first') },
      { color: 'var(--map-fill-2)', label: formatRange(q1, q2, 'middle') },
      { color: 'var(--map-fill-3)', label: formatRange(q2, q3, 'middle') },
      { color: 'var(--map-fill-4)', label: formatRange(q3, q4, 'middle') },
      { color: 'var(--map-fill-5)', label: formatRange(q4, maxValue, 'last') },
    ];
  }, [breaks, formatMetricValue, metricValues]);

  const styleForParish = useCallback(
    (name: string): L.PathOptions => {
      const rawValue = metricByParish[normalizeParishName(name)];
      const value = typeof rawValue === 'number' && Number.isFinite(rawValue) ? rawValue : null;
      const fills = palette.fills;
      const isSelected =
        Boolean(selectedParish) &&
        normalizeParishName(selectedParish as string) === normalizeParishName(name);

      let fillColor = fills[0];
      if (value === null) {
        fillColor = fills[0];
      } else if (value <= breaks[0]) {
        fillColor = fills[1];
      } else if (value <= breaks[1]) {
        fillColor = fills[2];
      } else if (value <= breaks[2]) {
        fillColor = fills[3];
      } else if (value <= breaks[3]) {
        fillColor = fills[4];
      } else {
        fillColor = fills[5];
      }

      return {
        fillColor,
        weight: isSelected ? 2 : 1,
        color: isSelected ? highlightColor : borderColor,
        fillOpacity: 0.8,
      };
    },
    [borderColor, breaks, highlightColor, metricByParish, palette, selectedParish],
  );

  const tooltipForParish = useCallback(
    (name: string) => {
      const rawValue = metricByParish[normalizeParishName(name)];
      const value = typeof rawValue === 'number' && Number.isFinite(rawValue) ? rawValue : null;
      const formattedValue = value === null ? 'N/A' : formatMetricValue(value);
      const safeName = escapeHtml(name);
      const safeMetricLabel = escapeHtml(metricLabel);
      const safeValue = escapeHtml(formattedValue);

      return `
        <div class="${styles.tooltipInner}">
          <span class="${styles.tooltipName}">${safeName}</span>
          <span class="${styles.tooltipMetric}">${safeMetricLabel}: ${safeValue}</span>
        </div>
      `.trim();
    },
    [formatMetricValue, metricByParish, metricLabel],
  );

  const assignTestId = useCallback((layer: L.Layer, name: string) => {
    const pathLayer = layer as L.Path & { getElement?: () => HTMLElement | null };
    const element = pathLayer.getElement?.();
    if (element) {
      element.setAttribute('data-testid', `parish-feature-${name}`);
      return;
    }

    if (typeof layer.once === 'function') {
      layer.once('add', () => {
        const target = pathLayer.getElement?.();
        if (target) {
          target.setAttribute('data-testid', `parish-feature-${name}`);
        }
      });
    }
  }, []);

  const accessibleParishNames = useMemo(() => {
    if (!geojson) {
      return [];
    }

    const names = new Set<string>();
    for (const feature of geojson.features ?? []) {
      names.add(toDisplayParishName(getFeatureName(feature)));
    }
    return Array.from(names).sort();
  }, [geojson]);

  const handleAccessibleSelect = useCallback(
    (name: string) => {
      setSelectedParish(name);
    },
    [setSelectedParish],
  );

  const svgPaths = useMemo(() => {
    if (!geojson) {
      return [];
    }

    const bounds = {
      minLon: Infinity,
      maxLon: -Infinity,
      minLat: Infinity,
      maxLat: -Infinity,
    };

    const walkCoords = (coords: unknown) => {
      if (!Array.isArray(coords)) {
        return;
      }
      if (coords.length >= 2 && typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        const lon = coords[0] as number;
        const lat = coords[1] as number;
        bounds.minLon = Math.min(bounds.minLon, lon);
        bounds.maxLon = Math.max(bounds.maxLon, lon);
        bounds.minLat = Math.min(bounds.minLat, lat);
        bounds.maxLat = Math.max(bounds.maxLat, lat);
        return;
      }
      coords.forEach(walkCoords);
    };

    geojson.features?.forEach((feature) => {
      const geometry = feature.geometry;
      if (!geometry) {
        return;
      }
      if (geometry.type === 'GeometryCollection') {
        geometry.geometries?.forEach((item) => {
          if ('coordinates' in item) {
            walkCoords(item.coordinates);
          }
        });
        return;
      }
      if ('coordinates' in geometry) {
        walkCoords(geometry.coordinates);
      }
    });

    if (!Number.isFinite(bounds.minLon) || !Number.isFinite(bounds.minLat)) {
      return [];
    }

    const viewSize = 1000;
    const spanLon = bounds.maxLon - bounds.minLon || 1;
    const spanLat = bounds.maxLat - bounds.minLat || 1;
    const scale = Math.min(viewSize / spanLon, viewSize / spanLat);
    const width = spanLon * scale;
    const height = spanLat * scale;
    const offsetX = (viewSize - width) / 2;
    const offsetY = (viewSize - height) / 2;

    const project = (lon: number, lat: number) => {
      const x = (lon - bounds.minLon) * scale + offsetX;
      const y = (bounds.maxLat - lat) * scale + offsetY;
      return [x, y];
    };

    const buildPath = (coords: number[][]) => {
      return coords
        .map(([lon, lat], index) => {
          const [x, y] = project(lon, lat);
          return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
        })
        .join(' ');
    };

    const paths: Array<{
      name: string;
      d: string;
      fill: string;
      stroke: string;
      strokeWidth: number;
    }> = [];

    geojson.features?.forEach((feature, index) => {
      const name = toDisplayParishName(getFeatureName(feature));
      const geom = feature.geometry;
      if (!geom) {
        return;
      }

      const normalized = normalizeParishName(name);
      const rawValue = metricByParish[normalized];
      const value = typeof rawValue === 'number' && Number.isFinite(rawValue) ? rawValue : null;
      const fills = palette.fills;
      let fill = fills[0];
      if (value === null) {
        fill = fills[0];
      } else if (value <= breaks[0]) {
        fill = fills[1];
      } else if (value <= breaks[1]) {
        fill = fills[2];
      } else if (value <= breaks[2]) {
        fill = fills[3];
      } else if (value <= breaks[3]) {
        fill = fills[4];
      } else {
        fill = fills[5];
      }

      const isSelected = selectedParish && normalizeParishName(selectedParish) === normalized;
      const stroke = isSelected ? highlightColor : borderColor;
      const strokeWidth = isSelected ? 2 : 1;

      if (geom.type === 'Polygon') {
        const rings = geom.coordinates as number[][][];
        const segments = rings.map((ring) => `${buildPath(ring)} Z`);
        paths.push({
          name: `${name}-${index}`,
          d: segments.join(' '),
          fill,
          stroke,
          strokeWidth,
        });
      }

      if (geom.type === 'MultiPolygon') {
        const polygons = geom.coordinates as number[][][][];
        const segments = polygons.flatMap((polygon) =>
          polygon.map((ring) => `${buildPath(ring)} Z`),
        );
        paths.push({
          name: `${name}-${index}`,
          d: segments.join(' '),
          fill,
          stroke,
          strokeWidth,
        });
      }
    });

    return paths;
  }, [breaks, borderColor, geojson, highlightColor, metricByParish, palette.fills, selectedParish]);

  useEffect(() => {
    styleForParishRef.current = styleForParish;
  }, [styleForParish]);

  const tileLayerUrl = useMemo(
    () =>
      theme === 'dark'
        ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    [theme],
  );
  const tileAttribution = useMemo(
    () =>
      theme === 'dark'
        ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    [theme],
  );

  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      const name = toDisplayParishName(getFeatureName(feature));

      const pathLayer = layer as L.Path;
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name));
      }

      assignTestId(layer, name);

      const tooltipText = tooltipForParish(name);
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined };
      const existingTooltip = typedLayer.getTooltip?.();
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText);
      } else {
        typedLayer.bindTooltip(tooltipText, {
          sticky: true,
          direction: 'top',
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
    [assignTestId, setSelectedParish, styleForParish, tooltipForParish],
  );

  useEffect(() => {
    if (
      !mapRef.current ||
      !mapNodeRef.current ||
      mapRef.current.getContainer() !== mapNodeRef.current
    ) {
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
      setMapReady(true);
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
        setMapReady(false);
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !mapReady) {
      return;
    }

    if (tileLayerRef.current) {
      tileLayerRef.current.remove();
    }

    const layer = L.tileLayer(tileLayerUrl, { attribution: tileAttribution });
    layer.addTo(mapRef.current);
    tileLayerRef.current = layer;
  }, [mapReady, tileAttribution, tileLayerUrl]);

  useEffect(() => {
    if (!mapRef.current || !geojson || !mapReady) {
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
    if (typeof layer.getBounds === 'function') {
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        mapRef.current.fitBounds(bounds, { padding: [16, 16], maxZoom: 11 });
        requestAnimationFrame(() => {
          mapRef.current?.invalidateSize();
        });
      }
    }
  }, [geojson, mapReady, onEachFeature]);

  useEffect(() => {
    if (!geoJsonLayerRef.current) {
      return;
    }

    geoJsonLayerRef.current.eachLayer((layer) => {
      const feature = (layer as L.Layer & { feature?: Feature }).feature;
      if (!feature) {
        return;
      }

      const name = toDisplayParishName(getFeatureName(feature));
      const pathLayer = layer as L.Path;
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name));
      }

      assignTestId(layer, name);

      const tooltipText = tooltipForParish(name);
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined };
      const existingTooltip = typedLayer.getTooltip?.();
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText);
      } else {
        typedLayer.bindTooltip(tooltipText, {
          sticky: true,
          direction: 'top',
          className: styles.tooltip,
          offset: L.point(0, -8),
          opacity: 1,
        });
      }
    });
  }, [assignTestId, styleForParish, tooltipForParish]);

  useEffect(() => {
    if (!mapRef.current || !mapReady) {
      return;
    }

    requestAnimationFrame(() => {
      mapRef.current?.invalidateSize();
    });
  }, [height, geojson, mapReady]);

  useEffect(() => {
    if (!geojson || !mapReady) {
      return;
    }

    const node = mapNodeRef.current;
    if (!node) {
      return;
    }

    const checkRendered = () => {
      const pathCount = node.querySelectorAll('path.leaflet-interactive').length;
      setUseSvgFallback(pathCount === 0);
    };

    const rafId = requestAnimationFrame(checkRendered);
    const timeoutId = window.setTimeout(checkRendered, 250);

    return () => {
      cancelAnimationFrame(rafId);
      window.clearTimeout(timeoutId);
    };
  }, [geojson, mapReady, selectedMetric, selectedParish]);

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

  const handleRetry = useCallback(() => {
    onRetry?.();
    loadGeometry(activeTenantId);
  }, [activeTenantId, loadGeometry, onRetry]);
  const clearParishFilter = useCallback(() => {
    setSelectedParish(undefined);
  }, [setSelectedParish]);

  const noDataLoaded = parishData.length === 0 && !geojson;
  const showSvgFallback = svgPaths.length > 0 && (useSvgFallback || !mapReady);

  if ((parishStatus === 'loading' || geometryStatus === 'loading') && noDataLoaded) {
    return (
      <div className="widget-skeleton" aria-busy="true">
        <Skeleton height="300px" borderRadius="1rem" />
      </div>
    );
  }

  if (geometryStatus === 'error' && noDataLoaded) {
    return (
      <DashboardState
        variant="error"
        message={geometryError ?? 'Unable to load parish boundaries.'}
        actionLabel="Retry load"
        onAction={handleRetry}
        layout="compact"
      />
    );
  }

  if (parishStatus === 'error' && parishData.length === 0) {
    return (
      <DashboardState
        variant="error"
        message={parishError ?? 'Unable to render the parish map.'}
        actionLabel="Retry load"
        onAction={handleRetry}
        layout="compact"
      />
    );
  }

  if (parishStatus === 'loading') {
    return <div className="status-message muted">Preparing the parish heatmap…</div>;
  }

  if (geometryStatus === 'loading' && !geojson) {
    return <div className="status-message muted">Loading parish boundaries…</div>;
  }

  if (geometryStatus === 'error' && !geojson) {
    return (
      <DashboardState
        variant="error"
        message={geometryError ?? 'Unable to load parish boundaries.'}
        actionLabel="Retry load"
        onAction={handleRetry}
        layout="compact"
      />
    );
  }

  if (parishData.length === 0) {
    return (
      <DashboardState
        variant="empty"
        icon={<MapPlaceholderIcon />}
        title="No map insights yet"
        message="Map insights will appear once this tenant has campaign data."
        actionLabel="Refresh data"
        onAction={handleRetry}
        actionVariant="secondary"
        layout="compact"
      />
    );
  }

  return (
    <div className={styles.mapShell} style={{ height }}>
      <div ref={mapNodeRef} className={`leaflet-container ${styles.map}`} />
      {showSvgFallback ? (
        <svg className={styles.mapSvg} viewBox="0 0 1000 1000" role="img" aria-label="Parish map">
          {svgPaths.map((path) => {
            const label = path.name.split('-')[0] ?? path.name;
            return (
              <path
                key={path.name}
                d={path.d}
                fill={path.fill}
                stroke={path.stroke}
                strokeWidth={path.strokeWidth}
                onClick={() => handleAccessibleSelect(label)}
              >
                <title>{label}</title>
              </path>
            );
          })}
        </svg>
      ) : null}
      <div className={styles.accessibilityList}>
        {accessibleParishNames.map((name) => (
          <button
            key={name}
            type="button"
            className={styles.accessibilityTrigger}
            data-testid={`parish-feature-${name}`}
            onClick={() => handleAccessibleSelect(name)}
          >
            {name}
          </button>
        ))}
      </div>

      <div className={styles.overlay}>
        <button
          type="button"
          className={styles.fullMapLink}
          onClick={clearParishFilter}
          disabled={!selectedParish}
          aria-label="Show all parishes"
        >
          All parishes
        </button>
        <Link to="/dashboards/map" className={styles.fullMapLink}>
          Open full map
        </Link>
        <button
          type="button"
          className={styles.toggleButton}
          onClick={toggleScrollZoom}
          aria-pressed={scrollZoomEnabled}
          aria-label={scrollZoomEnabled ? 'Disable scroll zoom' : 'Enable scroll zoom'}
        >
          <span aria-hidden="true" className={styles.toggleIcon}>
            <svg viewBox="0 0 24 24" role="img" focusable="false">
              <path d="M12 3a3 3 0 0 0-3 3v4.382a3 3 0 0 0-.879 2.12v5.5A2.998 2.998 0 0 0 10.5 21h3a2.998 2.998 0 0 0 2.379-1.498 2.998 2.998 0 0 0 .121-2.502v-5.498A3 3 0 0 0 15 10.382V6a3 3 0 0 0-3-3Zm-1.5 3a1.5 1.5 0 1 1 3 0v4.618a1.5 1.5 0 0 1-.439 1.061l-.061.06v.261h-2v-.26l-.061-.062A1.5 1.5 0 0 1 10.5 10.618Z" />
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
              <span
                className={styles.legendSwatch}
                style={{ backgroundColor: step.color }}
                aria-hidden="true"
              />
              <span className={styles.legendLabel}>{step.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default ParishMap;
