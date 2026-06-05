import { describe, expect, it } from 'vitest';

import {
  buildAssetHeatGrid,
  buildAssetTypePie,
  buildConvActionPie,
  buildFunnelStages,
  buildPmaxTreemapData,
  deriveHeatTone,
  rollupAssetKpis,
  rollupConversionKpis,
  rollupPmaxKpis,
} from './googleAdsCreativeConvAggregates';

describe('googleAdsCreativeConvAggregates', () => {
  describe('rollupAssetKpis', () => {
    it('returns zeros on empty input', () => {
      expect(rollupAssetKpis([])).toEqual({
        total: 0,
        disapproved: 0,
        topAssetConv: 0,
      });
    });
    it('counts disapproved and finds max conv', () => {
      const rows = [
        { asset_id: 'a', policy_approval_status: 'APPROVED', conversions: 3 },
        { asset_id: 'b', policy_approval_status: 'DISAPPROVED', conversions: 8 },
        { asset_id: 'c', policy_approval_status: 'AREA_OF_INTEREST_ONLY', conversions: 1 },
      ];
      expect(rollupAssetKpis(rows)).toEqual({
        total: 3,
        disapproved: 2,
        topAssetConv: 8,
      });
    });
  });

  describe('buildAssetTypePie', () => {
    it('aggregates counts by asset_type and sorts desc', () => {
      const rows = [{ asset_type: 'IMAGE' }, { asset_type: 'IMAGE' }, { asset_type: 'TEXT' }];
      expect(buildAssetTypePie(rows)).toEqual([
        { label: 'IMAGE', value: 2 },
        { label: 'TEXT', value: 1 },
      ]);
    });
    it('defaults missing asset_type to UNKNOWN', () => {
      expect(buildAssetTypePie([{ asset_id: 'a' }])).toEqual([{ label: 'UNKNOWN', value: 1 }]);
    });
  });

  describe('deriveHeatTone', () => {
    it('buckets ratios into low/medium/high', () => {
      expect(deriveHeatTone(0)).toBe('low');
      expect(deriveHeatTone(0.2)).toBe('low');
      expect(deriveHeatTone(0.5)).toBe('medium');
      expect(deriveHeatTone(0.9)).toBe('high');
      expect(deriveHeatTone(Number.NaN)).toBe('low');
    });
  });

  describe('buildAssetHeatGrid', () => {
    it('computes conv rate and intensity relative to max', () => {
      const rows = [
        {
          asset_id: 'a',
          asset_name: 'Hero',
          asset_type: 'IMAGE',
          clicks: 100,
          conversions: 10,
          impressions: 1000,
        }, // convRate = 0.1
        {
          asset_id: 'b',
          asset_name: 'Dud',
          asset_type: 'TEXT',
          clicks: 100,
          conversions: 1,
          impressions: 500,
        }, // convRate = 0.01
      ];
      const grid = buildAssetHeatGrid(rows);
      expect(grid).toHaveLength(2);
      const [hero, dud] = grid;
      expect(hero.convRate).toBeCloseTo(0.1, 5);
      expect(hero.intensity).toBeCloseTo(1, 5);
      expect(hero.tone).toBe('high');
      expect(dud.intensity).toBeCloseTo(0.1, 5);
      expect(dud.tone).toBe('low');
    });
    it('handles zero-click rows without dividing by zero', () => {
      const rows = [
        {
          asset_id: 'a',
          clicks: 0,
          conversions: 0,
          impressions: 10,
        },
      ];
      const grid = buildAssetHeatGrid(rows);
      expect(grid[0].convRate).toBe(0);
      expect(grid[0].intensity).toBe(0);
    });
  });

  describe('rollupPmaxKpis', () => {
    it('sums spend + conversions across rows', () => {
      const rows = [
        { asset_group_id: 'g1', spend: 100, conversions: 3 },
        { asset_group_id: 'g2', spend: 250.5, conversions: 7 },
      ];
      expect(rollupPmaxKpis(rows)).toEqual({
        totalGroups: 2,
        totalCost: 350.5,
        totalConversions: 10,
      });
    });
  });

  describe('buildPmaxTreemapData', () => {
    it('drops rows with non-positive spend and preserves spend/roas', () => {
      const rows = [
        { asset_group_name: 'A', spend: 500, roas: 1.5 },
        { asset_group_name: 'B', spend: 0, roas: 0 },
        { asset_group_name: 'C', spend: 100, roas: 0.4 },
      ];
      expect(buildPmaxTreemapData(rows)).toEqual([
        { name: 'A', spend: 500, roas: 1.5 },
        { name: 'C', spend: 100, roas: 0.4 },
      ]);
    });
  });

  describe('rollupConversionKpis', () => {
    it('computes totals and divide-safe avg CPA', () => {
      const rows = [
        { conversions: 10, value: 100, spend: 50 },
        { conversions: 20, conversion_value: 200, spend: 150 },
      ];
      expect(rollupConversionKpis(rows)).toEqual({
        totalConversions: 30,
        totalValue: 300,
        avgCpa: 200 / 30,
      });
    });
    it('returns zeros on empty input', () => {
      expect(rollupConversionKpis([])).toEqual({
        totalConversions: 0,
        totalValue: 0,
        avgCpa: 0,
      });
    });
  });

  describe('buildFunnelStages', () => {
    it('preserves ordered stages even with zeros', () => {
      expect(buildFunnelStages(undefined)).toEqual([
        { label: 'Impressions', value: 0 },
        { label: 'Clicks', value: 0 },
        { label: 'Conversions', value: 0 },
      ]);
    });
    it('reads metrics from summary', () => {
      expect(buildFunnelStages({ impressions: 1000, clicks: 40, conversions: 5 })).toEqual([
        { label: 'Impressions', value: 1000 },
        { label: 'Clicks', value: 40 },
        { label: 'Conversions', value: 5 },
      ]);
    });
  });

  describe('buildConvActionPie', () => {
    it('groups by conversion_action_name and sorts desc', () => {
      const rows = [
        { conversion_action_name: 'Purchase', conversions: 10 },
        { conversion_action_name: 'SignUp', conversions: 3 },
        { conversion_action_name: 'Purchase', conversions: 2 },
      ];
      expect(buildConvActionPie(rows)).toEqual([
        { label: 'Purchase', value: 12 },
        { label: 'SignUp', value: 3 },
      ]);
    });
    it('returns empty array for empty input', () => {
      expect(buildConvActionPie([])).toEqual([]);
    });
  });
});
