import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Feature, FeatureCollection } from 'geojson';
import L from 'leaflet';
import { Link } from 'react-router-dom';

import useDashboardStore, { type LoadStatus } from '../state/useDashboardStore';
import { formatCurrency, formatNumber, formatRatio } from '../lib/format';
import { fetchParishGeometry } from '../lib/dataService';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
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

function getFeatureName(feature: Feature): string {
  const name =
    typeof feature?.properties === 'object' && feature.properties !== null
      ? (feature.properties as { name?: unknown }).name
      : undefined;

  return typeof name === 'string' && name.length > 0 ? name : 'Unknown';
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
  if (value === 0) return 'var(--map-fill-0)';
  if (value <= breaks[0]) return 'var(--map-fill-1)';
  if (value <= breaks[1]) return 'var(--map-fill-2)';
  if (value <= breaks[2]) return 'var(--map-fill-3)';
  if (value <= breaks[3]) return 'var(--map-fill-4)';
  return 'var(--map-fill-5)';
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

  const borderColor = 'var(--map-border)';
  const highlightColor = 'var(--map-highlight)';

  const loadGeometry = useCallback((tenant?: string) => {
    geometryControllerRef.current?.abort();
    const controller = new AbortController();
    geometryControllerRef.current = controller;

    setGeometryStatus('loading');
    setGeometryError(undefined);

    fetchParishGeometry({
      path: withTenant('/dashboards/parish-geometry/', tenant),
      mockPath: '/jm_parishes.json',
      signal: controller.signal,
    })
      .then((data) => {
        setGeojson(data);
        setGeometryStatus('loaded');
        geometryControllerRef.current = null;
      })
      .catch(async (error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        try {
          const response = await fetch('/jm_parishes.json');
          if (response.ok) {
            const data = (await response.json()) as FeatureCollection;
            setGeojson(data);
            setGeometryStatus('loaded');
            geometryControllerRef.current = null;
            return;
          }
        } catch (fallbackError) {
          console.warn('Fallback parish geometry load failed', fallbackError);
        }

        console.error('Failed to load parish geometry', error);
        setGeometryStatus('error');
        setGeometryError(
          error instanceof Error ? error.message : 'Failed to load parish boundaries.',
        );
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
    return parishData.reduce<Record<string, number>>((acc, row) => {
      const key = row.parish;
      const value = Number(row[selectedMetric as keyof typeof row] ?? 0);
      acc[key] = value;
      return acc;
    }, {});
  }, [parishData, selectedMetric]);

  const metricValues = useMemo(() => Object.values(metricByParish), [metricByParish]);
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
    const [q1, q2, q3, q4] = breaks;
    const minValue = metricValues.length > 0 ? Math.min(...metricValues) : 0;

    const formatRange = (low: number, high: number, mode: 'first' | 'middle' | 'last') => {
      if (mode === 'first') {
        return `≤ ${formatMetricValue(high)}`;
      }
      if (mode === 'last') {
        return `> ${formatMetricValue(high)}`;
      }
      if (low === high) {
        return formatMetricValue(high);
      }
      return `${formatMetricValue(low)} – ${formatMetricValue(high)}`;
    };

    return [
      { color: 'var(--map-fill-0)', label: formatRange(minValue, q1, 'first') },
      { color: 'var(--map-fill-1)', label: formatRange(q1, q2, 'middle') },
      { color: 'var(--map-fill-2)', label: formatRange(q2, q3, 'middle') },
      { color: 'var(--map-fill-3)', label: formatRange(q3, q4, 'middle') },
      { color: 'var(--map-fill-4)', label: formatRange(q4, q4, 'last') },
    ];
  }, [breaks, formatMetricValue, metricValues]);

  const styleForParish = useCallback(
    (name: string): L.PathOptions => {
      const value = metricByParish[name] ?? 0;

      return {
        fillColor: getColor(value, breaks),
        weight: selectedParish === name ? 2 : 1,
        color: selectedParish === name ? highlightColor : borderColor,
        fillOpacity: 0.8,
      };
    },
    [borderColor, breaks, highlightColor, metricByParish, selectedParish],
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
      names.add(getFeatureName(feature));
    }
    return Array.from(names).sort();
  }, [geojson]);

  const handleAccessibleSelect = useCallback(
    (name: string) => {
      setSelectedParish(name);
    },
    [setSelectedParish],
  );

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
      const name = getFeatureName(feature);

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

  const handleRetry = useCallback(() => {
    onRetry?.();
    loadGeometry(activeTenantId);
  }, [activeTenantId, loadGeometry, onRetry]);

  const noDataLoaded = parishData.length === 0 && !geojson;

  if ((parishStatus === 'loading' || geometryStatus === 'loading') && noDataLoaded) {
    return (
      <div className="widget-skeleton" aria-busy="true">
        <Skeleton height="300px" borderRadius="1rem" />
      </div>
    );
  }

  if (geometryStatus === 'error' && noDataLoaded) {
    return (
      <ErrorState
        message={geometryError ?? 'Unable to load parish boundaries.'}
        onRetry={handleRetry}
        retryLabel="Retry load"
      />
    );
  }

  if (parishStatus === 'error' && parishData.length === 0) {
    return (
      <ErrorState
        message={parishError ?? 'Unable to render the parish map.'}
        onRetry={handleRetry}
        retryLabel="Retry load"
      />
    );
  }

  if (parishStatus === 'loading') {
    return <div className="status-message muted">Preparing the parish heatmap…</div>;
  }

  if (geometryStatus === 'loading' && !geojson) {
    return <div className="status-message muted">Loading parish boundaries…</div>;
  }

  if (parishData.length === 0) {
    return (
      <EmptyState
        icon={<MapPlaceholderIcon />}
        title="No map insights yet"
        message="Map insights will appear once this tenant has campaign data."
        actionLabel="Refresh data"
        onAction={handleRetry}
        actionVariant="secondary"
      />
    );
  }

  return (
    <div className={styles.mapShell} style={{ height }}>
      <div ref={mapNodeRef} className={`leaflet-container ${styles.map}`} />
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
