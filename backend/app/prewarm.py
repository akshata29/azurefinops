"""Pre-warm the permanent monthly cost-history store.

Fetches the full cost history once (QPU-paced) and persists every *closed*
month, so the dashboard never has to cold-start against the Cost Management
Query API. After a successful run, ordinary requests only refresh the current
(open) month — roughly 1 QPU per query instead of ~13.

    cd backend
    python -m app.prewarm                 # all accessible subscriptions
    python -m app.prewarm <subscription>  # a single subscription

It forces ``USE_MOCK=false`` for the process regardless of your .env. The run is
idempotent and resumable: already-persisted closed months are skipped, so if a
run is throttled part-way you can simply re-run it later to finish the backfill.
"""
from __future__ import annotations

import logging
import os
import sys
import time

os.environ["USE_MOCK"] = "false"

from app.config import get_settings  # noqa: E402
from app.services.azure_provider import AzureDataProvider  # noqa: E402

logger = logging.getLogger("prewarm")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if len(argv) > 1:
        os.environ["AZURE_SUBSCRIPTION_IDS"] = argv[1]
        get_settings.cache_clear()
        settings = get_settings()

    provider = AzureDataProvider(settings)
    client = provider.client
    months = getattr(provider, "_months", settings.history_months)
    targets = provider._targets(None)
    if not targets:
        print("No subscriptions found — check permissions / az login / AZURE_SUBSCRIPTION_IDS.")
        return 1

    cooldown = client.throttle_cooldown_remaining()
    if cooldown > 0:
        print(f"NOTE: a throttle cooldown is active ({cooldown:.0f}s). Backfill will wait it out as needed.")

    print(f"Pre-warming {len(targets)} subscription(s) x {months} months (QPU-paced; this can take a few minutes)...")
    started = time.time()
    warmed = 0
    gave_up = False

    for sid, tenant in targets:
        print(f"\n== {sid} (tenant {tenant or '-'}) ==")
        # block=True: wait out throttle cooldowns and retry until it actually
        # downloads, persisting each window as it succeeds.
        series = (
            ("monthly actual", lambda: client.monthly_totals(sid, months, amortized=False, tenant_id=tenant, block=True)),
            ("monthly amortized", lambda: client.monthly_totals(sid, months, amortized=True, tenant_id=tenant, block=True)),
            ("resource costs", lambda: client.resource_costs(sid, months, tenant_id=tenant, block=True)),
            ("pricing-model mix", lambda: client.dimension_totals(sid, "PricingModel", months, tenant_id=tenant, block=True)),
        )
        for label, fetch in series:
            t0 = time.time()
            try:
                rows = fetch()
                status = "OK  " if rows else "EMPTY"
                print(f"  {label:<19} {status} ({len(rows)} rows, {time.time() - t0:.1f}s)")
                if rows:
                    warmed += 1
                else:
                    gave_up = True
            except Exception as exc:  # pragma: no cover - permission/transient
                print(f"  {label:<19} FAILED: {exc}")
                gave_up = True

    print(f"\nDone in {time.time() - started:.0f}s. {warmed} series warmed.")
    if gave_up:
        rem = client.throttle_cooldown_remaining()
        print(f"Some series returned no data (cooldown ~{rem:.0f}s or a permission issue). Re-run `python -m app.prewarm` to continue.")
        return 2
    print("Closed months are persisted; the dashboard will now only refresh the open month.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
