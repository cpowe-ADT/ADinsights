"""Seed realistic Google Ads demo data into SDK tables.

Usage:
    python manage.py seed_google_ads_demo
    python manage.py seed_google_ads_demo --clear   # wipe and re-seed
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Tenant
from integrations.models import (
    GoogleAdsAccountMapping,
    GoogleAdsSdkAdGroupAdDaily,
    GoogleAdsSdkAssetGroupDaily,
    GoogleAdsSdkCampaignDaily,
    GoogleAdsSdkChangeEvent,
    GoogleAdsSdkConversionActionDaily,
    GoogleAdsSdkGeographicDaily,
    GoogleAdsSdkKeywordDaily,
    GoogleAdsSdkRecommendation,
    GoogleAdsSdkSearchTermDaily,
)

CUSTOMER_ID = "6715180623"
CURRENCY = "JMD"

CAMPAIGNS = [
    {
        "id": "20100001",
        "name": "Brand Awareness — Jamaica Tourism",
        "status": "ENABLED",
        "channel": "SEARCH",
        "daily_budget_micros": 45_000_000_000,
    },
    {
        "id": "20100002",
        "name": "Lead Gen — Real Estate Kingston",
        "status": "ENABLED",
        "channel": "SEARCH",
        "daily_budget_micros": 30_000_000_000,
    },
    {
        "id": "20100003",
        "name": "Ecommerce — Caribbean Spices Store",
        "status": "ENABLED",
        "channel": "PERFORMANCE_MAX",
        "daily_budget_micros": 60_000_000_000,
    },
    {
        "id": "20100004",
        "name": "Display — SLB Student Loans",
        "status": "ENABLED",
        "channel": "DISPLAY",
        "daily_budget_micros": 25_000_000_000,
    },
    {
        "id": "20100005",
        "name": "Video — Reggae Festival Promo",
        "status": "PAUSED",
        "channel": "VIDEO",
        "daily_budget_micros": 35_000_000_000,
    },
    {
        "id": "20100006",
        "name": "Shopping — Duty-Free Outlet",
        "status": "ENABLED",
        "channel": "SHOPPING",
        "daily_budget_micros": 50_000_000_000,
    },
]

AD_GROUPS = {
    "20100001": [
        {"ag_id": "30100001", "ads": [
            {"ad_id": "40100001", "name": "Visit Jamaica — Beach Getaway", "status": "ENABLED"},
            {"ad_id": "40100002", "name": "Jamaica Heritage Tours", "status": "ENABLED"},
        ]},
        {"ag_id": "30100002", "ads": [
            {"ad_id": "40100003", "name": "Montego Bay Hotels RSA", "status": "ENABLED"},
        ]},
    ],
    "20100002": [
        {"ag_id": "30100003", "ads": [
            {"ad_id": "40100004", "name": "Kingston Apartments — New Listings", "status": "ENABLED"},
            {"ad_id": "40100005", "name": "Waterfront Condos CTA", "status": "DISAPPROVED"},
        ]},
    ],
    "20100003": [
        {"ag_id": "30100004", "ads": [
            {"ad_id": "40100006", "name": "Jerk Seasoning — Free Shipping", "status": "ENABLED"},
            {"ad_id": "40100007", "name": "Hot Sauce Collection", "status": "ENABLED"},
        ]},
    ],
    "20100004": [
        {"ag_id": "30100005", "ads": [
            {"ad_id": "40100008", "name": "SLB Apply Now — Display Banner", "status": "ENABLED"},
        ]},
    ],
    "20100006": [
        {"ag_id": "30100006", "ads": [
            {"ad_id": "40100009", "name": "Rum & Cigars — Shopping Feed", "status": "ENABLED"},
            {"ad_id": "40100010", "name": "Blue Mountain Coffee — Shopping", "status": "ENABLED"},
        ]},
    ],
}

KEYWORDS = [
    {"campaign_id": "20100001", "ag_id": "30100001", "crit_id": "50100001", "text": "jamaica tourism", "match": "BROAD"},
    {"campaign_id": "20100001", "ag_id": "30100001", "crit_id": "50100002", "text": "visit jamaica", "match": "PHRASE"},
    {"campaign_id": "20100001", "ag_id": "30100002", "crit_id": "50100003", "text": "montego bay hotels", "match": "EXACT"},
    {"campaign_id": "20100002", "ag_id": "30100003", "crit_id": "50100004", "text": "kingston apartments for sale", "match": "BROAD"},
    {"campaign_id": "20100002", "ag_id": "30100003", "crit_id": "50100005", "text": "real estate jamaica", "match": "PHRASE"},
    {"campaign_id": "20100004", "ag_id": "30100005", "crit_id": "50100006", "text": "student loans jamaica", "match": "EXACT"},
    {"campaign_id": "20100004", "ag_id": "30100005", "crit_id": "50100007", "text": "slb application", "match": "BROAD"},
]

SEARCH_TERMS = [
    {"campaign_id": "20100001", "ag_id": "30100001", "text": "cheap flights to jamaica"},
    {"campaign_id": "20100001", "ag_id": "30100001", "text": "best beaches jamaica"},
    {"campaign_id": "20100001", "ag_id": "30100002", "text": "montego bay resorts all inclusive"},
    {"campaign_id": "20100002", "ag_id": "30100003", "text": "houses for sale kingston jamaica"},
    {"campaign_id": "20100002", "ag_id": "30100003", "text": "kingston apartment rent to own"},
    {"campaign_id": "20100004", "ag_id": "30100005", "text": "how to apply for slb loan"},
]

GEO_REGIONS = [
    ("Jamaica", "Kingston", "Kingston"),
    ("Jamaica", "St. Andrew", "Half Way Tree"),
    ("Jamaica", "St. James", "Montego Bay"),
    ("Jamaica", "St. Ann", "Ocho Rios"),
    ("Jamaica", "Westmoreland", "Negril"),
    ("Jamaica", "Portland", "Port Antonio"),
    ("Jamaica", "Manchester", "Mandeville"),
    ("United States", "Florida", "Miami"),
    ("United States", "New York", "New York"),
    ("United Kingdom", "England", "London"),
    ("Canada", "Ontario", "Toronto"),
]

ASSET_GROUPS = [
    {"campaign_id": "20100003", "ag_id": "60100001", "name": "Spice Collection — Default", "status": "ENABLED"},
    {"campaign_id": "20100003", "ag_id": "60100002", "name": "Hot Sauce — Listing Group", "status": "ENABLED"},
]

CONVERSION_ACTIONS = [
    {"id": "70100001", "name": "Purchase", "type": "WEBPAGE"},
    {"id": "70100002", "name": "Lead Form Submit", "type": "WEBPAGE"},
    {"id": "70100003", "name": "Phone Call", "type": "PHONE_CALL_TRACKING"},
    {"id": "70100004", "name": "Newsletter Signup", "type": "WEBPAGE"},
]

RECOMMENDATION_TYPES = [
    "KEYWORD",
    "RESPONSIVE_SEARCH_AD",
    "TARGET_CPA_OPT_IN",
    "MAXIMIZE_CONVERSIONS_OPT_IN",
    "SITELINK_EXTENSION",
]


def _date_range(days: int = 30) -> list[date]:
    today = date.today()
    return [today - timedelta(days=i) for i in range(days, 0, -1)]


def _jitter(base: int | float, pct: float = 0.25) -> int:
    low = int(base * (1 - pct))
    high = int(base * (1 + pct))
    return max(0, random.randint(low, high))


def _weekend_factor(d: date) -> float:
    return 0.6 if d.weekday() >= 5 else 1.0


def _trend_factor(day_index: int, total_days: int) -> float:
    return 0.85 + 0.15 * (day_index / max(total_days - 1, 1))


class Command(BaseCommand):
    help = "Seed realistic Google Ads demo data into SDK tables for dashboard development."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete existing demo data first")
        parser.add_argument("--days", type=int, default=30, help="Number of days to seed (default 30)")

    def handle(self, *args, **options):
        tenant = Tenant.objects.first()
        if not tenant:
            self.stderr.write("No tenant found. Create one first.")
            return

        days = options["days"]
        dates = _date_range(days)

        if options["clear"]:
            self.stdout.write("Clearing existing Google Ads demo data…")
            for model in (
                GoogleAdsSdkCampaignDaily,
                GoogleAdsSdkAdGroupAdDaily,
                GoogleAdsSdkGeographicDaily,
                GoogleAdsSdkKeywordDaily,
                GoogleAdsSdkSearchTermDaily,
                GoogleAdsSdkAssetGroupDaily,
                GoogleAdsSdkConversionActionDaily,
                GoogleAdsSdkChangeEvent,
                GoogleAdsSdkRecommendation,
                GoogleAdsAccountMapping,
            ):
                deleted, _ = model.objects.filter(tenant=tenant, customer_id=CUSTOMER_ID).delete()
                self.stdout.write(f"  {model.__name__}: {deleted} rows deleted")

        self.stdout.write(f"Seeding {days} days of Google Ads demo data for tenant {tenant.name}…")

        # Account mapping
        GoogleAdsAccountMapping.objects.update_or_create(
            tenant=tenant,
            customer_id=CUSTOMER_ID,
            defaults={
                "manager_customer_id": CUSTOMER_ID,
                "customer_name": "ADinsights Demo — Jamaica Agencies",
                "currency_code": CURRENCY,
                "time_zone": "America/Jamaica",
                "status": "ENABLED",
                "is_manager": True,
            },
        )
        self.stdout.write("  ✓ Account mapping created")

        # Campaign daily
        campaign_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for camp in CAMPAIGNS:
                if camp["status"] == "PAUSED" and d > date.today() - timedelta(days=10):
                    continue
                base_impressions = {"SEARCH": 4500, "DISPLAY": 18000, "VIDEO": 12000, "SHOPPING": 6000, "PERFORMANCE_MAX": 9000}.get(camp["channel"], 5000)
                impressions = _jitter(int(base_impressions * wf * tf))
                ctr = random.uniform(0.02, 0.08) if camp["channel"] == "SEARCH" else random.uniform(0.005, 0.025)
                clicks = max(1, int(impressions * ctr))
                avg_cpc_micros = _jitter({"SEARCH": 850_000_000, "DISPLAY": 250_000_000, "VIDEO": 180_000_000, "SHOPPING": 550_000_000, "PERFORMANCE_MAX": 650_000_000}.get(camp["channel"], 500_000_000), 0.3)
                cost_micros = clicks * avg_cpc_micros
                conv_rate = random.uniform(0.02, 0.06)
                conversions = Decimal(str(round(clicks * conv_rate, 2)))
                conv_value = Decimal(str(round(float(conversions) * random.uniform(3500, 12000), 2)))
                campaign_rows.append(GoogleAdsSdkCampaignDaily(
                    tenant=tenant,
                    customer_id=CUSTOMER_ID,
                    campaign_id=camp["id"],
                    campaign_name=camp["name"],
                    campaign_status=camp["status"],
                    advertising_channel_type=camp["channel"],
                    date_day=d,
                    currency_code=CURRENCY,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversions_value=conv_value,
                    cost_micros=cost_micros,
                ))
        GoogleAdsSdkCampaignDaily.objects.bulk_create(campaign_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(campaign_rows)} campaign daily rows")

        # Ad group ad daily
        ad_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for camp_id, ad_groups in AD_GROUPS.items():
                camp = next((c for c in CAMPAIGNS if c["id"] == camp_id), None)
                if not camp or (camp["status"] == "PAUSED" and d > date.today() - timedelta(days=10)):
                    continue
                for ag in ad_groups:
                    for ad in ag["ads"]:
                        impressions = _jitter(int(1500 * wf * tf))
                        clicks = max(1, int(impressions * random.uniform(0.02, 0.06)))
                        cost_micros = clicks * _jitter(600_000_000, 0.3)
                        conversions = Decimal(str(round(clicks * random.uniform(0.02, 0.05), 2)))
                        conv_value = Decimal(str(round(float(conversions) * random.uniform(4000, 10000), 2)))
                        approval = "APPROVED" if ad["status"] == "ENABLED" else "DISAPPROVED"
                        ad_rows.append(GoogleAdsSdkAdGroupAdDaily(
                            tenant=tenant,
                            customer_id=CUSTOMER_ID,
                            campaign_id=camp_id,
                            ad_group_id=ag["ag_id"],
                            ad_id=ad["ad_id"],
                            campaign_name=camp["name"],
                            ad_name=ad["name"],
                            ad_status=ad["status"],
                            policy_approval_status=approval,
                            policy_review_status="REVIEWED",
                            date_day=d,
                            currency_code=CURRENCY,
                            impressions=impressions,
                            clicks=clicks,
                            conversions=conversions,
                            conversions_value=conv_value,
                            cost_micros=cost_micros,
                        ))
        GoogleAdsSdkAdGroupAdDaily.objects.bulk_create(ad_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(ad_rows)} ad group ad daily rows")

        # Geographic daily
        geo_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for camp in CAMPAIGNS[:4]:
                if camp["status"] == "PAUSED" and d > date.today() - timedelta(days=10):
                    continue
                for country, region, city in GEO_REGIONS:
                    geo_weight = 1.0 if country == "Jamaica" else 0.3
                    impressions = _jitter(int(600 * wf * tf * geo_weight))
                    clicks = max(0, int(impressions * random.uniform(0.015, 0.05)))
                    cost_micros = clicks * _jitter(500_000_000, 0.3) if clicks else 0
                    conversions = Decimal(str(round(clicks * random.uniform(0.01, 0.04), 2))) if clicks else Decimal("0")
                    conv_value = Decimal(str(round(float(conversions) * random.uniform(3000, 8000), 2)))
                    geo_rows.append(GoogleAdsSdkGeographicDaily(
                        tenant=tenant,
                        customer_id=CUSTOMER_ID,
                        campaign_id=camp["id"],
                        date_day=d,
                        geo_target_country=country,
                        geo_target_region=region,
                        geo_target_city=city,
                        currency_code=CURRENCY,
                        impressions=impressions,
                        clicks=clicks,
                        conversions=conversions,
                        conversions_value=conv_value,
                        cost_micros=cost_micros,
                    ))
        GoogleAdsSdkGeographicDaily.objects.bulk_create(geo_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(geo_rows)} geographic daily rows")

        # Keyword daily
        kw_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for kw in KEYWORDS:
                impressions = _jitter(int(800 * wf * tf))
                clicks = max(1, int(impressions * random.uniform(0.03, 0.08)))
                cost_micros = clicks * _jitter(750_000_000, 0.3)
                conversions = Decimal(str(round(clicks * random.uniform(0.02, 0.06), 2)))
                conv_value = Decimal(str(round(float(conversions) * random.uniform(4000, 9000), 2)))
                kw_rows.append(GoogleAdsSdkKeywordDaily(
                    tenant=tenant,
                    customer_id=CUSTOMER_ID,
                    campaign_id=kw["campaign_id"],
                    ad_group_id=kw["ag_id"],
                    criterion_id=kw["crit_id"],
                    keyword_text=kw["text"],
                    match_type=kw["match"],
                    criterion_status="ENABLED",
                    quality_score=random.randint(5, 10),
                    ad_relevance=random.choice(["ABOVE_AVERAGE", "AVERAGE", "BELOW_AVERAGE"]),
                    expected_ctr=random.choice(["ABOVE_AVERAGE", "AVERAGE"]),
                    landing_page_experience=random.choice(["ABOVE_AVERAGE", "AVERAGE"]),
                    date_day=d,
                    currency_code=CURRENCY,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversions_value=conv_value,
                    cost_micros=cost_micros,
                ))
        GoogleAdsSdkKeywordDaily.objects.bulk_create(kw_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(kw_rows)} keyword daily rows")

        # Search term daily
        st_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for st in SEARCH_TERMS:
                impressions = _jitter(int(400 * wf * tf))
                clicks = max(0, int(impressions * random.uniform(0.02, 0.06)))
                cost_micros = clicks * _jitter(600_000_000, 0.3) if clicks else 0
                conversions = Decimal(str(round(clicks * random.uniform(0.01, 0.04), 2))) if clicks else Decimal("0")
                conv_value = Decimal(str(round(float(conversions) * random.uniform(3500, 8000), 2)))
                st_rows.append(GoogleAdsSdkSearchTermDaily(
                    tenant=tenant,
                    customer_id=CUSTOMER_ID,
                    campaign_id=st["campaign_id"],
                    ad_group_id=st["ag_id"],
                    search_term=st["text"],
                    date_day=d,
                    currency_code=CURRENCY,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversions_value=conv_value,
                    cost_micros=cost_micros,
                ))
        GoogleAdsSdkSearchTermDaily.objects.bulk_create(st_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(st_rows)} search term daily rows")

        # Asset group daily (PMax only)
        asset_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for ag in ASSET_GROUPS:
                impressions = _jitter(int(3000 * wf * tf))
                clicks = max(1, int(impressions * random.uniform(0.02, 0.05)))
                cost_micros = clicks * _jitter(550_000_000, 0.3)
                conversions = Decimal(str(round(clicks * random.uniform(0.03, 0.07), 2)))
                conv_value = Decimal(str(round(float(conversions) * random.uniform(5000, 12000), 2)))
                asset_rows.append(GoogleAdsSdkAssetGroupDaily(
                    tenant=tenant,
                    customer_id=CUSTOMER_ID,
                    campaign_id=ag["campaign_id"],
                    asset_group_id=ag["ag_id"],
                    asset_group_name=ag["name"],
                    asset_group_status=ag["status"],
                    date_day=d,
                    currency_code=CURRENCY,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    conversions_value=conv_value,
                    cost_micros=cost_micros,
                ))
        GoogleAdsSdkAssetGroupDaily.objects.bulk_create(asset_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(asset_rows)} asset group daily rows")

        # Conversion action daily
        conv_rows = []
        for day_idx, d in enumerate(dates):
            wf = _weekend_factor(d)
            tf = _trend_factor(day_idx, len(dates))
            for ca in CONVERSION_ACTIONS:
                base = {"WEBPAGE": 25, "PHONE_CALL_TRACKING": 8}.get(ca["type"], 12)
                conversions = Decimal(str(round(_jitter(int(base * wf * tf)) * random.uniform(0.8, 1.2), 2)))
                all_conv = conversions * Decimal("1.15")
                conv_value = Decimal(str(round(float(conversions) * random.uniform(4000, 15000), 2)))
                conv_rows.append(GoogleAdsSdkConversionActionDaily(
                    tenant=tenant,
                    customer_id=CUSTOMER_ID,
                    conversion_action_id=ca["id"],
                    conversion_action_name=ca["name"],
                    conversion_action_type=ca["type"],
                    date_day=d,
                    conversions=conversions,
                    all_conversions=all_conv,
                    conversions_value=conv_value,
                ))
        GoogleAdsSdkConversionActionDaily.objects.bulk_create(conv_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(conv_rows)} conversion action daily rows")

        # Change events (recent 14 days)
        change_rows = []
        operations = ["CREATE", "UPDATE", "UPDATE", "UPDATE", "REMOVE"]
        resource_types = ["CAMPAIGN", "AD_GROUP", "AD_GROUP_AD", "CAMPAIGN_BUDGET", "AD_GROUP_CRITERION"]
        for i in range(45):
            d = date.today() - timedelta(days=random.randint(0, 14))
            dt = datetime.combine(d, datetime.min.time().replace(
                hour=random.randint(8, 18),
                minute=random.randint(0, 59),
            ))
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
            fp = hashlib.md5(f"demo-change-{i}-{d}".encode()).hexdigest()[:16]
            camp = random.choice(CAMPAIGNS)
            change_rows.append(GoogleAdsSdkChangeEvent(
                tenant=tenant,
                customer_id=CUSTOMER_ID,
                event_fingerprint=fp,
                change_date_time=dt,
                user_email="agency-manager@adtelligent.net",
                client_type="GOOGLE_ADS_WEB_CLIENT",
                change_resource_type=random.choice(resource_types),
                resource_change_operation=random.choice(operations),
                campaign_id=camp["id"],
                changed_fields=["status", "name", "target_cpa_micros"][:random.randint(1, 3)],
            ))
        GoogleAdsSdkChangeEvent.objects.bulk_create(change_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(change_rows)} change events")

        # Recommendations
        rec_rows = []
        for i, rec_type in enumerate(RECOMMENDATION_TYPES):
            camp = CAMPAIGNS[i % len(CAMPAIGNS)]
            rec_rows.append(GoogleAdsSdkRecommendation(
                tenant=tenant,
                customer_id=CUSTOMER_ID,
                recommendation_type=rec_type,
                resource_name=f"customers/{CUSTOMER_ID}/recommendations/demo-{rec_type.lower()}-{i}",
                campaign_id=camp["id"],
                dismissed=False,
                impact_metadata={
                    "base_metrics": {"impressions": _jitter(5000), "clicks": _jitter(200), "cost_micros": _jitter(150_000_000_000)},
                    "potential_metrics": {"impressions": _jitter(7000), "clicks": _jitter(300), "cost_micros": _jitter(180_000_000_000)},
                },
            ))
        GoogleAdsSdkRecommendation.objects.bulk_create(rec_rows, ignore_conflicts=True)
        self.stdout.write(f"  ✓ {len(rec_rows)} recommendations")

        self.stdout.write(self.style.SUCCESS(f"\nDone! Seeded {days} days of Google Ads demo data for '{tenant.name}'."))
        self.stdout.write("Visit /dashboards/google-ads/executive to see the data.")
