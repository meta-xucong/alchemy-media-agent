from __future__ import annotations

import argparse
import time

from app.config import ensure_runtime_dirs, settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID
from app.services.bootstrap import bootstrap_v2_repository
from app.services.resource_sync import sync_resource_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Custom Media Agent 2.0 provider sync worker.")
    parser.add_argument("--provider-id", default=EVOLINKAI_PROVIDER_ID)
    parser.add_argument("--mode", choices=["auto", "seed", "remote"], default="auto")
    parser.add_argument("--once", action="store_true", help="Run one provider sync and exit.")
    parser.add_argument("--interval-minutes", type=int, default=settings.resource_sync_interval_minutes)
    args = parser.parse_args()

    ensure_runtime_dirs()
    bootstrap_v2_repository(seed_cases=True)

    while True:
        try:
            result = sync_resource_provider(args.provider_id, mode=args.mode)  # type: ignore[arg-type]
            print(
                {
                    "provider_id": result.provider_id,
                    "sync_run_id": result.sync_run_id,
                    "status": result.status,
                    "source_version": result.source_version,
                    "stats": result.stats,
                },
                flush=True,
            )
        except Exception as exc:
            print({"provider_id": args.provider_id, "status": "failed", "error": repr(exc)}, flush=True)

        if args.once:
            return
        time.sleep(max(60, args.interval_minutes * 60))


if __name__ == "__main__":
    main()
