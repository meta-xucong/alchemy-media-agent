#!/usr/bin/env python3
"""Read-only verification of prepared V2 history/favorites projections."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--history-path", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.data_root.is_dir() or not args.history_path.parent.is_dir():
        parser.error("--data-root and --history-path parent must be existing directories")
    data_root = args.data_root.resolve()
    history_path = args.history_path.resolve()
    os.environ["V2_DATA_DIR"] = str(data_root)
    os.environ["V2_IMAGE_HISTORY_PATH"] = str(history_path)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_media_agent_2_0"))
    try:
        from app.services.history_read_maintenance import verify_history_reads

        result = verify_history_reads(data_root, history_path)
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
