from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import urllib.request


MODELS = {
    "face_detection_yunet_2023mar.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "YUNET_LICENSE": "https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/LICENSE",
    "SFACE_LICENSE": "https://raw.githubusercontent.com/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/LICENSE",
}


def fetch_models(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in MODELS.items():
        target = target_dir / filename
        if target.exists():
            continue
        with tempfile.NamedTemporaryFile(dir=target_dir, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            urllib.request.urlretrieve(url, temporary_path)
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
