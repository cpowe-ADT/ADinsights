import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer } from 'react-leaflet'
import type { Feature, FeatureCollection } from 'geojson'
import L from 'leaflet'

import useDashboardStore from '../features/dashboard/store/useDashboardStore'
import { formatCurrency, formatNumber, formatRatio } from '../lib/format'
import StatusMessage from './ui/StatusMessage'

const JAMAICA_CENTER: [number, number] = [18.1096, -77.2975]
const MAP_COLORS = ['#ecfdf9', '#aaf0e6', '#5fdbc9', '#2bb39f', '#0c7769']

function getFeatureName(feature: Feature): string {
  const name =
    typeof feature?.properties === 'object' && feature.properties !== null
      ? (feature.properties as { name?: unknown }).name
      : undefined

  return typeof name === 'string' && name.length > 0 ? name : 'Unknown'
}

function computeBreaks(values: number[]): number[] {
  if (values.length === 0) {
    return [0, 0, 0, 0]
  }
  const sorted = [...values].sort((a, b) => a - b)
  const quantile = (p: number) => {
    const idx = Math.floor(p * (sorted.length - 1))
    return sorted[idx]
  }
  return [quantile(0.25), quantile(0.5), quantile(0.75), quantile(0.9)]
}

function getColor(value: number, breaks: number[]): string {
  if (value === 0) return MAP_COLORS[0]
  if (value <= breaks[0]) return MAP_COLORS[1]
  if (value <= breaks[1]) return MAP_COLORS[2]
  if (value <= breaks[2]) return MAP_COLORS[3]
  if (value <= breaks[3]) return MAP_COLORS[4]
  return '#065f54'
}

const ParishMap = () => {
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
  }))
  const [geojson, setGeojson] = useState<FeatureCollection | null>(null)
  const geoJsonRef = useRef<L.GeoJSON | null>(null)
  const styleForParishRef = useRef<(name: string) => L.PathOptions>(() => ({
    color: '#0f172a',
    weight: 1,
    fillColor: MAP_COLORS[0],
    fillOpacity: 0.8,
  }))

  useEffect(() => {
    fetch('/jm_parishes.json')
      .then((res) => res.json())
      .then((data: FeatureCollection) => setGeojson(data))
      .catch((error) => console.error('Failed to load GeoJSON', error))
  }, [])

  const metricByParish = useMemo(() => {
    return parishData.reduce<Record<string, number>>((acc, row) => {
      const key = row.parish
      const value = Number(row[selectedMetric as keyof typeof row] ?? 0)
      acc[key] = value
      return acc
    }, {})
  }, [parishData, selectedMetric])

  const breaks = useMemo(() => computeBreaks(Object.values(metricByParish)), [metricByParish])

  const styleForParish = useCallback(
    (name: string): L.PathOptions => {
      const value = metricByParish[name] ?? 0

      return {
        fillColor: getColor(value, breaks),
        weight: selectedParish === name ? 2 : 1,
        color: selectedParish === name ? '#f97066' : '#0f172a',
        fillOpacity: 0.8,
      }
    },
    [breaks, metricByParish, selectedParish],
  )

  const tooltipForParish = useCallback(
    (name: string) => {
      const value = metricByParish[name] ?? 0
      const currency = parishData[0]?.currency ?? 'USD'
      const labels: Record<string, string> = {
        spend: 'Spend',
        impressions: 'Impressions',
        clicks: 'Clicks',
        conversions: 'Conversions',
        roas: 'ROAS',
      }

      const formattedValue =
        selectedMetric === 'spend'
          ? formatCurrency(value, currency)
          : selectedMetric === 'roas'
            ? formatRatio(value, 2)
            : formatNumber(value)

      const label = labels[selectedMetric] ?? selectedMetric.toUpperCase()
      return `${name}<br/>${label}: ${formattedValue}`
    },
    [metricByParish, selectedMetric, parishData],
  )

  useEffect(() => {
    styleForParishRef.current = styleForParish
  }, [styleForParish])

  const onEachFeature = useCallback(
    (feature: Feature, layer: L.Layer) => {
      const name = getFeatureName(feature)

      const pathLayer = layer as L.Path
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name))
      }

      const tooltipText = tooltipForParish(name)
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined }
      const existingTooltip = typedLayer.getTooltip?.()
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText)
      } else {
        typedLayer.bindTooltip(tooltipText, { sticky: true })
      }

      layer.on({
        click: () => setSelectedParish(name),
        mouseover: () => {
          pathLayer.setStyle({ weight: Math.max(pathLayer.options.weight ?? 1, 2) })
        },
        mouseout: () => {
          pathLayer.setStyle(styleForParishRef.current(name))
        },
      })
    },
    [setSelectedParish, styleForParish, tooltipForParish],
  )

  useEffect(() => {
    if (!geoJsonRef.current) {
      return
    }

    geoJsonRef.current.eachLayer((layer) => {
      const feature = (layer as L.Layer & { feature?: Feature }).feature
      if (!feature) {
        return
      }

      const name = getFeatureName(feature)
      const pathLayer = layer as L.Path
      if (pathLayer.setStyle) {
        pathLayer.setStyle(styleForParish(name))
      }

      const tooltipText = tooltipForParish(name)
      const typedLayer = layer as L.Layer & { getTooltip?: () => L.Tooltip | undefined }
      const existingTooltip = typedLayer.getTooltip?.()
      if (existingTooltip) {
        existingTooltip.setContent(tooltipText)
      } else {
        typedLayer.bindTooltip(tooltipText, { sticky: true })
      }
    })
  }, [styleForParish, tooltipForParish])

  if (parishStatus === 'loading') {
    return <StatusMessage variant="muted">Preparing the parish heatmap…</StatusMessage>
  }

  if (parishStatus === 'error') {
    return (
      <StatusMessage variant="error">
        {parishError ?? 'Unable to render the parish map.'}
      </StatusMessage>
    )
  }

  if (parishData.length === 0) {
    return (
      <StatusMessage variant="muted">
        Map insights will appear once this tenant has campaign data.
      </StatusMessage>
    )
  }

  return (
    <MapContainer
      center={JAMAICA_CENTER}
      zoom={7}
      scrollWheelZoom={false}
      style={{ height: '100%', width: '100%' }}
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
  )
}

export default ParishMap
