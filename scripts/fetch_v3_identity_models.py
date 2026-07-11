from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tempfile
import urllib.request


MODELS = {
    "face_detection_yunet_2023mar.onnx": {
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    },
    "face_recognition_sface_2021dec.onnx": {
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "sha256": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    },
    "YUNET_LICENSE": {
        "url": "https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/LICENSE",
        "sha256": "c83b8120c50ccbd4c4f96edf53141bdd566ebb8f8e9227e415326aa1b1aba958",
    },
    "SFACE_LICENSE": {
        "url": "https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/LICENSE",
        "sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_models(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, spec in MODELS.items():
        target = target_dir / filename
        if target.exists() and _sha256(target) == spec["sha256"]:
            continue
        with tempfile.NamedTemporaryFile(dir=target_dir, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            urllib.request.urlretrieve(spec["url"], temporary_path)
            actual = _sha256(temporary_path)
            if actual != spec["sha256"]:
                raise RuntimeError(f"SHA-256 mismatch for {filename}: {actual}")
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch pinned V3 identity evaluation models.")
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    fetch_models(args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
