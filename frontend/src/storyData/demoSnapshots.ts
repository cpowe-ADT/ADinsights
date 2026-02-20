export type DemoTenantKey = 'bank-of-jamaica' | 'grace-kennedy' | 'jdic';

export interface DemoTenantSnapshot {
  id: DemoTenantKey;
  label: string;
  metrics: {
    campaign: {
      summary: {
        currency: string;
        totalSpend: number;
        totalImpressions: number;
        totalClicks: number;
        totalConversions: number;
        averageRoas: number;
      };
      trend: Array<{
        date: string;
        spend: number;
        conversions: number;
        clicks: number;
        impressions: number;
      }>;
      rows: Array<{
        id: string;
        name: string;
        platform: string;
        status: string;
        parish: string;
        spend: number;
        impressions: number;
        clicks: number;
        conversions: number;
        roas: number;
        ctr?: number;
        cpc?: number;
        cpm?: number;
        objective?: string;
        startDate?: string;
        endDate?: string;
      }>;
    };
    creative: Array<{
      id: string;
      name: string;
      campaignId: string;
      campaignName: string;
      platform: string;
      parish: string;
      spend: number;
      impressions: number;
      clicks: number;
      conversions: number;
      roas: number;
      ctr?: number;
    }>;
    budget: Array<{
      id: string;
      campaignName: string;
      parishes: string[];
      monthlyBudget: number;
      spendToDate: number;
      projectedSpend: number;
      pacingPercent: number;
      startDate: string;
      endDate: string;
    }>;
    parish: Array<{
      parish: string;
      spend: number;
      impressions: number;
      clicks: number;
      conversions: number;
      roas: number;
      campaignCount: number;
      currency: string;
    }>;
  };
}

export const demoSnapshots: Record<DemoTenantKey, DemoTenantSnapshot> = {
  'bank-of-jamaica': {
    id: 'bank-of-jamaica',
    label: 'Bank of Jamaica',
    metrics: {
      campaign: {
        summary: {
          currency: 'JMD',
          totalSpend: 4_200_000,
          totalImpressions: 1_850_000,
          totalClicks: 86_000,
          totalConversions: 5_400,
          averageRoas: 4.2,
        },
        trend: [
          {
            date: '2024-09-01',
            spend: 780_000,
            conversions: 980,
            clicks: 16_200,
            impressions: 310_000,
          },
          {
            date: '2024-09-02',
            spend: 690_000,
            conversions: 910,
            clicks: 15_400,
            impressions: 295_000,
          },
          {
            date: '2024-09-03',
            spend: 640_000,
            conversions: 870,
            clicks: 14_950,
            impressions: 288_000,
          },
        ],
        rows: [
          {
            id: 'boj_fx_awareness',
            name: 'FX Market Awareness',
            platform: 'Meta',
            status: 'Active',
            parish: 'Kingston',
            spend: 1_200_000,
            impressions: 540_000,
            clicks: 24_500,
            conversions: 1_600,
            roas: 3.9,
            ctr: 0.045,
            cpc: 49.0,
            cpm: 222.0,
            objective: 'Awareness',
            startDate: '2024-08-01',
            endDate: '2024-09-30',
          },
          {
            id: 'boj_policy_updates',
            name: 'Policy Update Series',
            platform: 'Google Ads',
            status: 'Active',
            parish: 'St Andrew',
            spend: 980_000,
            impressions: 460_000,
            clicks: 22_100,
            conversions: 1_420,
            roas: 4.5,
            ctr: 0.048,
            cpc: 44.4,
            cpm: 213.0,
            objective: 'Traffic',
            startDate: '2024-08-10',
            endDate: '2024-09-28',
          },
          {
            id: 'boj_digital_payments',
            name: 'Digital Payments Launch',
            platform: 'TikTok',
            status: 'Learning',
            parish: 'St James',
            spend: 880_000,
            impressions: 410_000,
            clicks: 18_900,
            conversions: 1_350,
            roas: 4.1,
            ctr: 0.046,
            cpc: 46.6,
            cpm: 214.6,
            objective: 'Acquisition',
            startDate: '2024-08-18',
            endDate: '2024-10-05',
          },
        ],
      },
      creative: [
        {
          id: 'boj_fx_video',
          name: 'FX Explainer Video',
          campaignId: 'boj_fx_awareness',
          campaignName: 'FX Market Awareness',
          platform: 'Meta',
          parish: 'Kingston',
          spend: 420_000,
          impressions: 210_000,
          clicks: 10_200,
          conversions: 680,
          roas: 3.6,
          ctr: 0.0486,
        },
        {
          id: 'boj_policy_search',
          name: 'Policy Hub Search',
          campaignId: 'boj_policy_updates',
          campaignName: 'Policy Update Series',
          platform: 'Google Ads',
          parish: 'St Andrew',
          spend: 360_000,
          impressions: 176_000,
          clicks: 8_600,
          conversions: 540,
          roas: 4.2,
          ctr: 0.0489,
        },
      ],
      budget: [
        {
          id: 'boj_fx_awareness_budget',
          campaignName: 'FX Market Awareness',
          parishes: ['Kingston', 'St Andrew'],
          monthlyBudget: 1_500_000,
          spendToDate: 1_200_000,
          projectedSpend: 1_480_000,
          pacingPercent: 0.99,
          startDate: '2024-08-01',
          endDate: '2024-09-30',
        },
        {
          id: 'boj_digital_payments_budget',
          campaignName: 'Digital Payments Launch',
          parishes: ['St James', 'Manchester'],
          monthlyBudget: 1_200_000,
          spendToDate: 880_000,
          projectedSpend: 1_185_000,
          pacingPercent: 0.95,
          startDate: '2024-08-15',
          endDate: '2024-10-05',
        },
      ],
      parish: [
        {
          parish: 'Kingston',
          spend: 1_500_000,
          impressions: 720_000,
          clicks: 31_800,
          conversions: 2_050,
          roas: 4.0,
          campaignCount: 2,
          currency: 'JMD',
        },
        {
          parish: 'St Andrew',
          spend: 1_100_000,
          impressions: 520_000,
          clicks: 23_800,
          conversions: 1_580,
          roas: 4.4,
          campaignCount: 2,
          currency: 'JMD',
        },
        {
          parish: 'St James',
          spend: 800_000,
          impressions: 410_000,
          clicks: 18_900,
          conversions: 1_350,
          roas: 4.1,
          campaignCount: 1,
          currency: 'JMD',
        },
      ],
    },
  },
  'grace-kennedy': {
    id: 'grace-kennedy',
    label: 'GraceKennedy',
    metrics: {
      campaign: {
        summary: {
          currency: 'USD',
          totalSpend: 310_000,
          totalImpressions: 1_450_000,
          totalClicks: 92_000,
          totalConversions: 7_200,
          averageRoas: 5.1,
        },
        trend: [
          {
            date: '2024-09-01',
            spend: 98_000,
            conversions: 2_300,
            clicks: 31_200,
            impressions: 480_000,
          },
          {
            date: '2024-09-02',
            spend: 102_000,
            conversions: 2_400,
            clicks: 30_500,
            impressions: 520_000,
          },
          {
            date: '2024-09-03',
            spend: 110_000,
            conversions: 2_500,
            clicks: 30_300,
            impressions: 450_000,
          },
        ],
        rows: [
          {
            id: 'gk_foods_autumn',
            name: 'Grace Foods Autumn Push',
            platform: 'Meta',
            status: 'Active',
            parish: 'St Catherine',
            spend: 150_000,
            impressions: 620_000,
            clicks: 41_000,
            conversions: 3_200,
            roas: 4.7,
            ctr: 0.066,
            cpc: 3.65,
            cpm: 242.0,
            objective: 'Awareness',
            startDate: '2024-08-12',
            endDate: '2024-10-15',
          },
          {
            id: 'gk_financial_services',
            name: 'GK Money Services',
            platform: 'Google Ads',
            status: 'Active',
            parish: 'Kingston',
            spend: 90_000,
            impressions: 420_000,
            clicks: 29_500,
            conversions: 2_100,
            roas: 5.6,
            ctr: 0.07,
            cpc: 3.05,
            cpm: 214.0,
            objective: 'Leads',
            startDate: '2024-08-01',
            endDate: '2024-09-30',
          },
          {
            id: 'gk_remittances',
            name: 'Western Union Remittances',
            platform: 'TikTok',
            status: 'Active',
            parish: 'St James',
            spend: 70_000,
            impressions: 410_000,
            clicks: 21_500,
            conversions: 1_900,
            roas: 5.1,
            ctr: 0.052,
            cpc: 3.25,
            cpm: 170.7,
            objective: 'Acquisition',
            startDate: '2024-08-20',
            endDate: '2024-10-01',
          },
        ],
      },
      creative: [
        {
          id: 'gk_autumn_recipe',
          name: 'Autumn Recipe Series',
          campaignId: 'gk_foods_autumn',
          campaignName: 'Grace Foods Autumn Push',
          platform: 'Meta',
          parish: 'St Catherine',
          spend: 64_000,
          impressions: 280_000,
          clicks: 18_600,
          conversions: 1_340,
          roas: 4.3,
          ctr: 0.066,
        },
        {
          id: 'gk_money_search',
          name: 'Money Services Search',
          campaignId: 'gk_financial_services',
          campaignName: 'GK Money Services',
          platform: 'Google Ads',
          parish: 'Kingston',
          spend: 42_000,
          impressions: 190_000,
          clicks: 14_100,
          conversions: 980,
          roas: 5.2,
          ctr: 0.074,
        },
      ],
      budget: [
        {
          id: 'gk_foods_budget',
          campaignName: 'Grace Foods Autumn Push',
          parishes: ['St Catherine', 'Clarendon'],
          monthlyBudget: 180_000,
          spendToDate: 150_000,
          projectedSpend: 176_000,
          pacingPercent: 0.98,
          startDate: '2024-08-12',
          endDate: '2024-10-15',
        },
        {
          id: 'gk_money_budget',
          campaignName: 'GK Money Services',
          parishes: ['Kingston', 'St Andrew'],
          monthlyBudget: 120_000,
          spendToDate: 90_000,
          projectedSpend: 118_000,
          pacingPercent: 0.98,
          startDate: '2024-08-01',
          endDate: '2024-09-30',
        },
      ],
      parish: [
        {
          parish: 'St Catherine',
          spend: 160_000,
          impressions: 650_000,
          clicks: 43_000,
          conversions: 3_300,
          roas: 4.9,
          campaignCount: 2,
          currency: 'USD',
        },
        {
          parish: 'Kingston',
          spend: 90_000,
          impressions: 420_000,
          clicks: 29_500,
          conversions: 2_100,
          roas: 5.6,
          campaignCount: 1,
          currency: 'USD',
        },
        {
          parish: 'St James',
          spend: 60_000,
          impressions: 380_000,
          clicks: 19_500,
          conversions: 1_800,
          roas: 4.9,
          campaignCount: 1,
          currency: 'USD',
        },
      ],
    },
  },
  jdic: {
    id: 'jdic',
    label: 'JDIC',
    metrics: {
      campaign: {
        summary: {
          currency: 'JMD',
          totalSpend: 1_800_000,
          totalImpressions: 920_000,
          totalClicks: 51_000,
          totalConversions: 3_100,
          averageRoas: 3.7,
        },
        trend: [
          {
            date: '2024-09-01',
            spend: 320_000,
            conversions: 520,
            clicks: 9_200,
            impressions: 160_000,
          },
          {
            date: '2024-09-02',
            spend: 290_000,
            conversions: 500,
            clicks: 8_900,
            impressions: 150_000,
          },
          {
            date: '2024-09-03',
            spend: 310_000,
            conversions: 540,
            clicks: 9_300,
            impressions: 155_000,
          },
        ],
        rows: [
          {
            id: 'jdic_depositor_protection',
            name: 'Depositor Protection',
            platform: 'Meta',
            status: 'Active',
            parish: 'Kingston',
            spend: 620_000,
            impressions: 320_000,
            clicks: 17_800,
            conversions: 1_050,
            roas: 3.4,
            ctr: 0.055,
            cpc: 34.8,
            cpm: 193.7,
            objective: 'Awareness',
            startDate: '2024-08-05',
            endDate: '2024-09-30',
          },
          {
            id: 'jdic_fdic_comparison',
            name: 'FDIC Comparison',
            platform: 'Google Ads',
            status: 'Active',
            parish: 'St Andrew',
            spend: 560_000,
            impressions: 280_000,
            clicks: 17_200,
            conversions: 980,
            roas: 3.9,
            ctr: 0.061,
            cpc: 32.6,
            cpm: 200.0,
            objective: 'Education',
            startDate: '2024-08-10',
            endDate: '2024-09-28',
          },
          {
            id: 'jdic_youth_finance',
            name: 'Youth Financial Literacy',
            platform: 'TikTok',
            status: 'Active',
            parish: 'Manchester',
            spend: 420_000,
            impressions: 320_000,
            clicks: 16_000,
            conversions: 1_070,
            roas: 3.8,
            ctr: 0.05,
            cpc: 26.3,
            cpm: 131.3,
            objective: 'Engagement',
            startDate: '2024-08-15',
            endDate: '2024-09-30',
          },
        ],
      },
      creative: [
        {
          id: 'jdic_depositor_video',
          name: 'Depositor Video Story',
          campaignId: 'jdic_depositor_protection',
          campaignName: 'Depositor Protection',
          platform: 'Meta',
          parish: 'Kingston',
          spend: 240_000,
          impressions: 140_000,
          clicks: 7_800,
          conversions: 480,
          roas: 3.3,
          ctr: 0.055,
        },
        {
          id: 'jdic_youth_tiktok',
          name: 'Youth Finance Tips',
          campaignId: 'jdic_youth_finance',
          campaignName: 'Youth Financial Literacy',
          platform: 'TikTok',
          parish: 'Manchester',
          spend: 180_000,
          impressions: 135_000,
          clicks: 6_500,
          conversions: 420,
          roas: 3.6,
          ctr: 0.048,
        },
      ],
      budget: [
        {
          id: 'jdic_depositor_budget',
          campaignName: 'Depositor Protection',
          parishes: ['Kingston', 'St Andrew'],
          monthlyBudget: 750_000,
          spendToDate: 620_000,
          projectedSpend: 732_000,
          pacingPercent: 0.98,
          startDate: '2024-08-05',
          endDate: '2024-09-30',
        },
        {
          id: 'jdic_youth_budget',
          campaignName: 'Youth Financial Literacy',
          parishes: ['Manchester', 'St Elizabeth'],
          monthlyBudget: 500_000,
          spendToDate: 420_000,
          projectedSpend: 498_000,
          pacingPercent: 0.996,
          startDate: '2024-08-15',
          endDate: '2024-09-30',
        },
      ],
      parish: [
        {
          parish: 'Kingston',
          spend: 630_000,
          impressions: 330_000,
          clicks: 18_100,
          conversions: 1_080,
          roas: 3.5,
          campaignCount: 2,
          currency: 'JMD',
        },
        {
          parish: 'St Andrew',
          spend: 560_000,
          impressions: 285_000,
          clicks: 17_500,
          conversions: 1_000,
          roas: 3.9,
          campaignCount: 1,
          currency: 'JMD',
        },
        {
          parish: 'Manchester',
          spend: 420_000,
          impressions: 320_000,
          clicks: 16_000,
          conversions: 1_070,
          roas: 3.8,
          campaignCount: 1,
          currency: 'JMD',
        },
      ],
    },
  },
};

export const demoTenants = Object.values(demoSnapshots).map(({ id, label }) => ({
  id,
  label,
}));

export const defaultDemoTenant: DemoTenantKey = 'bank-of-jamaica';

export function getDemoSnapshot(tenant: DemoTenantKey): DemoTenantSnapshot {
  return demoSnapshots[tenant] ?? demoSnapshots[defaultDemoTenant];
}
