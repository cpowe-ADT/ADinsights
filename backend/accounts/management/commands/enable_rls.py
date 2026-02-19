from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection

TENANT_TABLES = [
    "accounts_user",
    "accounts_userrole",
    "accounts_auditlog",
    "integrations_platformcredential",
    "integrations_apierrorlog",
    "accounts_tenantkey",
    "analytics_adaccount",
    "analytics_campaign",
    "analytics_adset",
    "analytics_ad",
    "analytics_rawperformancerecord",
]


class Command(BaseCommand):
    help = "Enable row level security policies for tenant scoped tables"

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(
                self.style.WARNING("RLS only supported on PostgreSQL; skipping.")
            )
            return
        with connection.cursor() as cursor:
            for table in TENANT_TABLES:
                self.stdout.write(f"Enabling RLS on {table}")
                cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
                policy_sql = (
                    "CREATE POLICY tenant_isolation ON {table} USING "
                    "(tenant_id = current_setting('app.tenant_id')::uuid)"
                ).format(table=table)
                cursor.execute(
                    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = current_schema() "
                    "AND tablename = %s AND policyname = 'tenant_isolation') THEN "
                    + policy_sql
                    + "; END IF; END $$;",
                    [table.split(".")[-1]],
                )
                self.stdout.write(self.style.SUCCESS(f"Policy ensured for {table}"))
