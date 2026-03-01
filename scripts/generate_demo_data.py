#!/usr/bin/env python3
"""Generate deterministic demo CSVs for dbt seeds."""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from faker import Faker


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "dbt" / "seeds" / "demo"
DEFAULT_END_DATE = date(2024, 9, 30)

PARISHES = [
    "Kingston",
    "St Andrew",
    "St Catherine",
    "Clarendon",
    "Manchester",
    "St Ann",
    "St Mary",
    "Portland",
    "St Thomas",
    "St James",
    "Hanover",
    "Westmoreland",
    "Trelawny",
    "St Elizabeth",
]

PARISH_WEIGHTS = [
    1.8,
    1.7,
    1.6,
    1.1,
    1.0,
    1.0,
    0.85,
    0.8,
    0.75,
    1.2,
    0.6,
    0.7,
    0.65,
    0.9,
]

CHANNELS = ["Meta", "Google Ads", "TikTok", "YouTube"]
OBJECTIVES = ["Awareness", "Traffic", "Leads", "Sales", "Video Views"]
CREATIVE_TYPES = ["image", "video", "carousel"]

TENANTS = [
    {
        "tenant_id": "bank-of-jamaica",
        "tenant_name": "Bank of Jamaica",
        "currency": "JMD",
        "timezone": "America/Jamaica",
        "snapshot_offset_days": 0,
    },
    {
        "tenant_id": "grace-kennedy",
        "tenant_name": "GraceKennedy",
        "currency": "USD",
        "timezone": "America/Jamaica",
        "snapshot_offset_days": 1,
    },
    {
        "tenant_id": "jdic",
        "tenant_name": "JDIC",
        "currency": "JMD",
        "timezone": "America/Jamaica",
        "snapshot_offset_days": 8,
    },
]

CHANNEL_PROFILES = {
    "Meta": {"cpm": (350, 900), "ctr": (0.008, 0.025), "cvr": (0.01, 0.05)},
    "Google Ads": {"cpm": (500, 1400), "ctr": (0.01, 0.035), "cvr": (0.015, 0.07)},
    "TikTok": {"cpm": (280, 800), "ctr": (0.006, 0.02), "cvr": (0.008, 0.04)},
    "YouTube": {"cpm": (250, 700), "ctr": (0.004, 0.015), "cvr": (0.004, 0.02)},
}

WEEKDAY_MULTIPLIERS = {
    0: 0.9,
    1: 1.0,
    2: 1.05,
    3: 1.1,
    4: 1.2,
    5: 0.95,
    6: 0.85,
}


@dataclass
class CampaignProfile:
    tenant_id: str
    campaign_id: str
    channel: str
    campaign_name: str
    objective: str
    status: str
    start_date: date
    end_date: date | None
    parish: str | None
    daily_budget: float
    base_cpm: float
    base_ctr: float
    base_cvr: float
    aov: float


@dataclass
class GenerationConfig:
    out_dir: Path
    days: int
    seed: int
    end_date: date

    @property
    def start_date(self) -> date:
        return self.end_date - timedelta(days=self.days - 1)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic demo CSVs for dbt seeds.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--end-date",
        type=lambda value: date.fromisoformat(value),
        default=DEFAULT_END_DATE,
        help="Anchor end date (YYYY-MM-DD) for deterministic outputs.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation checks after writing CSVs.",
    )
    return parser.parse_args(argv)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def daterange(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]


def month_starts(start: date, end: date) -> list[date]:
    months = []
    current = date(start.year, start.month, 1)
    while current <= end:
        months.append(current)
        next_month = current.replace(day=28) + timedelta(days=4)
        current = next_month.replace(day=1)
    return months


def random_dirichlet(rng: random.Random, weights: Sequence[float]) -> list[float]:
    gamma_samples = [rng.gammavariate(weight, 1.0) for weight in weights]
    total = sum(gamma_samples)
    if total == 0:
        return [1.0 / len(weights)] * len(weights)
    return [value / total for value in gamma_samples]


def clamp_rate(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_campaigns(
    rng: random.Random,
    fake: Faker,
    config: GenerationConfig,
) -> tuple[list[CampaignProfile], list[dict[str, object]]]:
    campaigns: list[CampaignProfile] = []
    rows: list[dict[str, object]] = []

    for tenant in TENANTS:
        tenant_id = tenant["tenant_id"]
        currency = tenant["currency"]
        campaign_count = rng.randint(9, 13)
        missing_parish_campaign = rng.randint(0, campaign_count - 1)

        for index in range(campaign_count):
            channel = rng.choice(CHANNELS)
            objective = rng.choice(OBJECTIVES)
            status = "PAUSED" if rng.random() < 0.15 else "ACTIVE"
            campaign_id = f"{tenant_id[:3].upper()}-{index + 1:03d}"
            campaign_name = f"{fake.company()} {fake.bs().title()}"
            start_offset = rng.randint(15, 75)
            start_date = config.start_date - timedelta(days=start_offset)
            end_date = None if status == "ACTIVE" else config.start_date + timedelta(days=rng.randint(20, 60))
            parish = "" if index == missing_parish_campaign else rng.choice(PARISHES)

            budget_base = 18000 if currency == "JMD" else 550
            budget_span = 42000 if currency == "JMD" else 1600
            daily_budget = rng.uniform(budget_base, budget_base + budget_span)

            profile = CHANNEL_PROFILES[channel]
            base_cpm = rng.uniform(*profile["cpm"])
            base_ctr = rng.uniform(*profile["ctr"])
            base_cvr = rng.uniform(*profile["cvr"])
            if objective in {"Awareness", "Video Views"}:
                base_cvr = rng.uniform(0.0, 0.01)

            aov_base = 2500 if currency == "JMD" else 40
            aov_span = 8000 if currency == "JMD" else 140
            aov = rng.uniform(aov_base, aov_base + aov_span)

            campaigns.append(
                CampaignProfile(
                    tenant_id=tenant_id,
                    campaign_id=campaign_id,
                    channel=channel,
                    campaign_name=campaign_name,
                    objective=objective,
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    parish=parish or None,
                    daily_budget=daily_budget,
                    base_cpm=base_cpm,
                    base_ctr=base_ctr,
                    base_cvr=base_cvr,
                    aov=aov,
                )
            )

            rows.append(
                {
                    "tenant_id": tenant_id,
                    "campaign_id": campaign_id,
                    "channel": channel,
                    "campaign_name": campaign_name,
                    "objective": objective,
                    "status": status,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat() if end_date else "",
                    "parish": parish,
                }
            )

    return campaigns, rows


def build_creatives(
    rng: random.Random,
    fake: Faker,
    campaigns: Sequence[CampaignProfile],
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    rows: list[dict[str, object]] = []
    by_campaign: dict[str, list[dict[str, object]]] = {}

    for campaign in campaigns:
        creative_count = rng.randint(3, 7)
        for index in range(creative_count):
            creative_id = f"CR-{campaign.campaign_id}-{index + 1:02d}"
            creative_type = rng.choice(CREATIVE_TYPES)
            creative_name = fake.catch_phrase()
            row = {
                "tenant_id": campaign.tenant_id,
                "campaign_id": campaign.campaign_id,
                "channel": campaign.channel,
                "creative_id": creative_id,
                "creative_name": creative_name,
                "creative_type": creative_type,
            }
            rows.append(row)
            by_campaign.setdefault(campaign.campaign_id, []).append(row)

    return rows, by_campaign


def generate_metrics(
    rng: random.Random,
    campaigns: Sequence[CampaignProfile],
    creatives_by_campaign: dict[str, list[dict[str, object]]],
    config: GenerationConfig,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    daily_campaign_rows: list[dict[str, object]] = []
    daily_creative_rows: list[dict[str, object]] = []
    daily_parish_rows: list[dict[str, object]] = []
    daily_channel_totals: dict[tuple[str, str, date], dict[str, float]] = {}

    dates = daterange(config.start_date, config.days)
    spike_tenant = TENANTS[0]["tenant_id"]
    spike_start = config.start_date + timedelta(days=max(0, config.days // 2 - 3))
    spike_window = {spike_start + timedelta(days=offset) for offset in range(7)}
    missing_parish_date = config.start_date + timedelta(days=min(10, config.days - 1))

    tenant_snapshots = {
        tenant["tenant_id"]: (config.end_date - timedelta(days=tenant["snapshot_offset_days"]))
        for tenant in TENANTS
    }

    zero_spend_campaigns = {
        campaigns[0].campaign_id if campaigns else None,
        campaigns[-1].campaign_id if campaigns else None,
    }

    for campaign in campaigns:
        for current_date in dates:
            is_spike = campaign.tenant_id == spike_tenant and current_date in spike_window
            weekday_factor = WEEKDAY_MULTIPLIERS.get(current_date.weekday(), 1.0)
            noise = rng.uniform(0.7, 1.25)
            spend = campaign.daily_budget * weekday_factor * noise
            if is_spike:
                spend *= 2.6
            if campaign.status == "PAUSED" or campaign.campaign_id in zero_spend_campaigns:
                spend = 0.0
            if rng.random() < 0.015:
                spend = 0.0
            spend = round(spend, 2)

            cpm = campaign.base_cpm * rng.uniform(0.9, 1.12)
            ctr = clamp_rate(campaign.base_ctr * rng.uniform(0.85, 1.2), 0.002, 0.08)
            cvr = clamp_rate(campaign.base_cvr * rng.uniform(0.8, 1.3), 0.0, 0.12)

            impressions = int((spend / cpm) * 1000) if spend > 0 else 0
            clicks = int(impressions * ctr) if impressions > 0 else 0
            conversions = int(clicks * cvr) if clicks > 0 else 0
            revenue = round(conversions * campaign.aov, 2)
            roas = round(revenue / spend, 2) if spend > 0 else 0.0

            snapshot_generated_at = datetime.combine(
                tenant_snapshots[campaign.tenant_id],
                datetime.min.time(),
            ).isoformat() + "Z"

            daily_campaign_rows.append(
                {
                    "date": current_date.isoformat(),
                    "tenant_id": campaign.tenant_id,
                    "channel": campaign.channel,
                    "campaign_id": campaign.campaign_id,
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "revenue": revenue,
                    "roas": roas,
                    "snapshot_generated_at": snapshot_generated_at,
                }
            )

            totals_key = (campaign.tenant_id, campaign.channel, current_date)
            totals = daily_channel_totals.setdefault(
                totals_key,
                {"spend": 0.0, "impressions": 0.0, "clicks": 0.0, "conversions": 0.0, "revenue": 0.0},
            )
            totals["spend"] += spend
            totals["impressions"] += impressions
            totals["clicks"] += clicks
            totals["conversions"] += conversions
            totals["revenue"] += revenue

            if spend > 0:
                creatives = creatives_by_campaign.get(campaign.campaign_id, [])
                if creatives:
                    weights = random_dirichlet(rng, [2.5] * len(creatives))
                    for creative, weight in zip(creatives, weights):
                        cr_spend = round(spend * weight, 2)
                        cr_impressions = int(impressions * weight)
                        cr_clicks = int(clicks * weight)
                        cr_conversions = int(conversions * weight)
                        cr_revenue = round(revenue * weight, 2)
                        cr_roas = round(cr_revenue / cr_spend, 2) if cr_spend > 0 else 0.0
                        daily_creative_rows.append(
                            {
                                "date": current_date.isoformat(),
                                "tenant_id": campaign.tenant_id,
                                "channel": campaign.channel,
                                "campaign_id": campaign.campaign_id,
                                "creative_id": creative["creative_id"],
                                "creative_type": creative["creative_type"],
                                "spend": cr_spend,
                                "impressions": cr_impressions,
                                "clicks": cr_clicks,
                                "conversions": cr_conversions,
                                "revenue": cr_revenue,
                                "roas": cr_roas,
                            }
                        )

    for (tenant_id, channel, current_date), totals in daily_channel_totals.items():
        if totals["spend"] <= 0:
            continue

        missing_share = 0.0
        if tenant_id == TENANTS[1]["tenant_id"] and current_date == missing_parish_date:
            missing_share = 0.05
            missing_spend = totals["spend"] * missing_share
            missing_impressions = int(totals["impressions"] * missing_share)
            missing_clicks = int(totals["clicks"] * missing_share)
            missing_conversions = int(totals["conversions"] * missing_share)
            missing_revenue = round(totals["revenue"] * missing_share, 2)
            missing_roas = round(missing_revenue / missing_spend, 2) if missing_spend > 0 else 0.0
            daily_parish_rows.append(
                {
                    "date": current_date.isoformat(),
                    "tenant_id": tenant_id,
                    "channel": channel,
                    "parish": "",
                    "spend": round(missing_spend, 2),
                    "impressions": missing_impressions,
                    "clicks": missing_clicks,
                    "conversions": missing_conversions,
                    "revenue": missing_revenue,
                    "roas": missing_roas,
                }
            )

        remainder = 1.0 - missing_share
        weights = random_dirichlet(rng, PARISH_WEIGHTS)
        for parish, weight in zip(PARISHES, weights):
            spend = round(totals["spend"] * weight * remainder, 2)
            impressions = int(totals["impressions"] * weight * remainder)
            clicks = int(totals["clicks"] * weight * remainder)
            conversions = int(totals["conversions"] * weight * remainder)
            revenue = round(totals["revenue"] * weight * remainder, 2)
            roas = round(revenue / spend, 2) if spend > 0 else 0.0
            daily_parish_rows.append(
                {
                    "date": current_date.isoformat(),
                    "tenant_id": tenant_id,
                    "channel": channel,
                    "parish": parish,
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "revenue": revenue,
                    "roas": roas,
                }
            )

    return daily_campaign_rows, daily_creative_rows, daily_parish_rows, []


def build_budgets(
    rng: random.Random,
    campaigns: Sequence[CampaignProfile],
    config: GenerationConfig,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    months = month_starts(config.start_date, config.end_date)

    for campaign in campaigns:
        for month_start in months:
            next_month = month_start.replace(day=28) + timedelta(days=4)
            month_end = next_month.replace(day=1) - timedelta(days=1)
            days_in_month = month_end.day
            budget_factor = rng.uniform(0.75, 1.25)
            planned_budget = campaign.daily_budget * days_in_month * budget_factor
            rows.append(
                {
                    "month": month_start.isoformat(),
                    "tenant_id": campaign.tenant_id,
                    "channel": campaign.channel,
                    "campaign_id": campaign.campaign_id,
                    "planned_budget": round(planned_budget, 2),
                }
            )

    return rows


def build_tenants(config: GenerationConfig) -> list[dict[str, object]]:
    rows = []
    for tenant in TENANTS:
        snapshot_date = config.end_date - timedelta(days=tenant["snapshot_offset_days"])
        snapshot_timestamp = datetime.combine(snapshot_date, datetime.min.time()).isoformat() + "Z"
        rows.append(
            {
                "tenant_id": tenant["tenant_id"],
                "tenant_name": tenant["tenant_name"],
                "currency": tenant["currency"],
                "timezone": tenant["timezone"],
                "snapshot_generated_at": snapshot_timestamp,
            }
        )
    return rows


def validate_outputs(out_dir: Path) -> None:
    expected_files = [
        "dim_tenants.csv",
        "dim_campaigns.csv",
        "dim_creatives.csv",
        "fact_daily_campaign_metrics.csv",
        "fact_daily_parish_metrics.csv",
        "fact_daily_creative_metrics.csv",
        "plan_monthly_budgets.csv",
    ]

    for name in expected_files:
        path = out_dir / name
        if not path.exists():
            raise SystemExit(f"Missing expected output: {path}")

    with (out_dir / "dim_tenants.csv").open(encoding="utf-8") as handle:
        reader = list(csv.DictReader(handle))
        if len(reader) < 2:
            raise SystemExit("Expected at least two tenants in dim_tenants.csv")

    with (out_dir / "fact_daily_campaign_metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        if not any(row.get("spend") in {"0", "0.0", "0.00"} for row in rows):
            raise SystemExit("Expected at least one zero-spend row in fact_daily_campaign_metrics.csv")

    with (out_dir / "fact_daily_parish_metrics.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        parishes = {row.get("parish", "") for row in rows if row.get("parish")}
        missing = [parish for parish in PARISHES if parish not in parishes]
        if missing:
            raise SystemExit(f"Missing parishes in fact_daily_parish_metrics.csv: {', '.join(missing)}")
        if not any(row.get("parish", "") == "" for row in rows):
            raise SystemExit("Expected at least one row with missing parish in fact_daily_parish_metrics.csv")


def generate(config: GenerationConfig) -> None:
    rng = random.Random(config.seed)
    fake = Faker()
    fake.seed_instance(config.seed)

    tenant_rows = build_tenants(config)
    campaigns, campaign_rows = build_campaigns(rng, fake, config)
    creative_rows, creatives_by_campaign = build_creatives(rng, fake, campaigns)
    (
        daily_campaign_rows,
        daily_creative_rows,
        daily_parish_rows,
        _,
    ) = generate_metrics(rng, campaigns, creatives_by_campaign, config)
    budget_rows = build_budgets(rng, campaigns, config)

    out_dir = config.out_dir

    write_csv(
        out_dir / "dim_tenants.csv",
        ["tenant_id", "tenant_name", "currency", "timezone", "snapshot_generated_at"],
        tenant_rows,
    )
    write_csv(
        out_dir / "dim_campaigns.csv",
        [
            "tenant_id",
            "campaign_id",
            "channel",
            "campaign_name",
            "objective",
            "status",
            "start_date",
            "end_date",
            "parish",
        ],
        campaign_rows,
    )
    write_csv(
        out_dir / "dim_creatives.csv",
        [
            "tenant_id",
            "campaign_id",
            "channel",
            "creative_id",
            "creative_name",
            "creative_type",
        ],
        creative_rows,
    )
    write_csv(
        out_dir / "fact_daily_campaign_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "campaign_id",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
            "snapshot_generated_at",
        ],
        daily_campaign_rows,
    )
    write_csv(
        out_dir / "fact_daily_parish_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "parish",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
        ],
        daily_parish_rows,
    )
    write_csv(
        out_dir / "fact_daily_creative_metrics.csv",
        [
            "date",
            "tenant_id",
            "channel",
            "campaign_id",
            "creative_id",
            "creative_type",
            "spend",
            "impressions",
            "clicks",
            "conversions",
            "revenue",
            "roas",
        ],
        daily_creative_rows,
    )
    write_csv(
        out_dir / "plan_monthly_budgets.csv",
        ["month", "tenant_id", "channel", "campaign_id", "planned_budget"],
        budget_rows,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = GenerationConfig(
        out_dir=args.out,
        days=max(1, args.days),
        seed=args.seed,
        end_date=args.end_date,
    )

    generate(config)

    if args.validate:
        validate_outputs(config.out_dir)

    print(f"Generated demo seed CSVs in {config.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
