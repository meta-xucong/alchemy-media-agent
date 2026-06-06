from __future__ import annotations

import argparse
import time

from app.agents import CreativeManagerRuntime
from app.config import ensure_runtime_dirs, settings
from app.services.bootstrap import bootstrap_v2_repository
from app.services.queue_worker import process_next_task_once
from app.services.task_queue import initialize_task_queue


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Custom Media Agent 2.0 persistent task worker.")
    parser.add_argument("--worker-id", default="v2-standalone-worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued task and exit.")
    parser.add_argument("--sleep", type=float, default=settings.task_queue_poll_interval_seconds)
    args = parser.parse_args()

    ensure_runtime_dirs()
    bootstrap_v2_repository(seed_cases=True)
    initialize_task_queue()
    runtime = CreativeManagerRuntime()

    while True:
        processed = process_next_task_once(runtime, args.worker_id)
        if args.once or not processed:
            if args.once:
                return
            time.sleep(max(0.1, args.sleep))


if __name__ == "__main__":
    main()
