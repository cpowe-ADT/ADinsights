# Data Contract Validation Evidence

Date: 2026-02-06 (America/Jamaica)

## Command

```bash
python3 infrastructure/airbyte/scripts/check_data_contracts.py
```

## Result

- Exit code: `0`
- Output: `Data-contract validation passed.`

## Coverage

1. Google Ads query alias mapping checks (`google_ads_source.yaml`, packaged SQL template).
2. Google Ads lookback env-name consistency (`LOOKBACK_WINDOW_DAYS` canonical).
3. Raw seed header checks for Meta/Google staging compatibility.
4. CSV alias parity checks between backend and frontend parsers.
5. CSV runbook path + Data Sources link target checks.
