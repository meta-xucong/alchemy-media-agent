from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_disabled_mcp_accepts_utf8_reference_filename_before_mode_gate(tmp_path: Path) -> None:
    reference = tmp_path / "真实人物参考图_正面.png"
    reference.write_bytes(b"not-a-pixel-fixture")
    request = {
        "jsonrpc": "2.0",
        "id": 133,
        "method": "tools/call",
        "params": {
            "name": "prepare_native_imagegen_plan",
            "arguments": {
                "user_input": "Prepare a portrait identity planning request.",
                "template_id": "general_template",
                "requested_image_count": 1,
                "requested_image_size": "1024x1024",
                "reference_inputs": [
                    {"channel": "portrait_identity", "file_path": str(reference)},
                ],
            },
        },
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "plugins" / "alchemy-codex-local-mode" / "scripts" / "start_mcp.py"),
        ],
        cwd=ROOT,
        env={**os.environ, "ALCHEMY_CODEX_LOCAL_REPO_ROOT": str(ROOT)},
        input=json.dumps(request, ensure_ascii=False) + "\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    response = json.loads(completed.stdout.strip())
    text = response["result"]["content"][0]["text"]
    assert json.loads(text)["code"] == "codex_native_imagegen_mode_disabled"
