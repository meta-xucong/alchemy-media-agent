from __future__ import annotations

import argparse
import time

from app.config import ensure_runtime_dirs, settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_thumbnail_prewarm import prewarm_case_thumbnails
from app.services.resource_sync import sync_resource_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Custom Media Agent 2.0 provider sync worker.")
    parser.add_argument("--provider-id", default=EVOLINKAI_PROVIDER_ID)
    parser.add_argument("--mode", choices=["auto", "seed", "remote"], default="auto")
    parser.add_argument("--once", action="store_true", help="Run one provider sync and exit.")
    parser.add_argument("--interval-minutes", type=int, default=settings.resource_sync_interval_minutes)
    parser.add_argument("--prewarm-only", action="store_true", help="Only prewarm case thumbnails for the current index.")
    parser.add_argument("--skip-prewarm", action="store_true", help="Skip thumbnail prewarm after a successful sync.")
    parser.add_argument("--prewarm-limit", type=int, default=settings.case_thumbnail_prewarm_limit)
    parser.add_argument("--prewarm-variant", default=settings.case_thumbnail_prewarm_variant)
    args = parser.parse_args()

    ensure_runtime_dirs()
    bootstrap_v2_repository(seed_cases=True)

    while True:
        try:
            if args.prewarm_only:
                prewarm = prewarm_case_thumbnails(variant=args.prewarm_variant, limit=max(0, args.prewarm_limit))
                print({"provider_id": args.provider_id, "status": "prewarmed", "thumbnail_prewarm": prewarm.as_dict()}, flush=True)
                if args.once:
                    return
                time.sleep(max(60, args.interval_minutes * 60))
                continue

            result = sync_resource_provider(args.provider_id, mode=args.mode)  # type: ignore[arg-type]
            prewarm_payload = None
            if result.status == "completed" and settings.case_thumbnail_prewarm_enabled and not args.skip_prewarm:
                prewarm = prewarm_case_thumbnails(variant=args.prewarm_variant, limit=max(0, args.prewarm_limit))
                prewarm_payload = prewarm.as_dict()
            print(
                {
                    "provider_id": result.provider_id,
                    "sync_run_id": result.sync_run_id,
                    "status": result.status,
                    "source_version": result.source_version,
                    "stats": result.stats,
                    "thumbnail_prewarm": prewarm_payload,
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
