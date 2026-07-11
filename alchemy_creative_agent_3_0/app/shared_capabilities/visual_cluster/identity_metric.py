"""Ephemeral, commercially compatible portrait identity metrics for Doc96."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from .contracts import IdentityMetricResult


YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"
CALIBRATION_VERSION = "doc96_sface_cosine_v1"


class SFaceIdentityMetricProvider:
    """Compute current-request identity evidence without persisting vectors."""

    provider_name = "opencv_yunet_sface"

    def __init__(self, *, model_dir: str | Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir is not None else _configured_model_dir()
        self._detector = None
        self._recognizer = None
        self._cv = None

    def available(self) -> bool:
        if not _metric_enabled():
            return False
        if not self._model_path(YUNET_FILENAME).is_file() or not self._model_path(SFACE_FILENAME).is_file():
            return False
        try:
            self._load()
        except Exception:
            return False
        return True

    def evaluate(self, output_path: str | Path, reference_paths: list[str | Path]) -> IdentityMetricResult:
        if not self.available():
            return IdentityMetricResult(
                status="unavailable",
                reason_codes=["identity_metric_unavailable"],
                metadata={"provider": self.provider_name, "calibration_version": CALIBRATION_VERSION},
            )
        try:
            output_image = self._read_image(Path(output_path))
            output_faces = self._detect(output_image)
            reference_candidates: list[tuple[Any, Any, int]] = []
            total_reference_faces = 0
            for reference_index, value in enumerate(reference_paths):
                image = self._read_image(Path(value))
                faces = self._detect(image)
                total_reference_faces += len(faces)
                if faces:
                    reference_candidates.append((image, self._select_face(faces), reference_index))
            if not output_faces:
                return self._unavailable("output_face_not_detected", total_reference_faces, 0)
            if not reference_candidates:
                return self._unavailable("reference_face_not_detected", 0, len(output_faces))

            output_face_index, output_face = self._select_face_with_index(output_faces)
            output_feature = self._feature(output_image, output_face)
            scored: list[tuple[float, float, Any, int]] = []
            for reference_image, reference_face, reference_index in reference_candidates:
                reference_feature = self._feature(reference_image, reference_face)
                raw = float(
                    self._recognizer.match(
                        reference_feature,
                        output_feature,
                        self._cv.FaceRecognizerSF_FR_COSINE,
                    )
                )
                scored.append((raw, _geometry_similarity(reference_face, output_face), reference_face, reference_index))
            raw, geometry, reference_face, reference_index = max(scored, key=lambda item: item[0])
            calibrated = _calibrate_sface_cosine(raw)
            detection_confidence = min(float(reference_face[-1]), float(output_face[-1]))
            metric_confidence = max(0.0, min(1.0, detection_confidence * (0.9 if len(output_faces) == 1 else 0.78)))
            reason_codes: list[str] = []
            if len(output_faces) > 1:
                reason_codes.append("multiple_output_faces_metric_subject_selected")
            if calibrated < 0.72:
                reason_codes.append("identity_metric_low")
            elif calibrated < 0.82:
                reason_codes.append("identity_metric_below_commercial_target")
            return IdentityMetricResult(
                status="pass" if calibrated >= 0.82 else "warning" if calibrated >= 0.72 else "fail",
                calibrated_score=round(calibrated, 4),
                raw_cosine_similarity=round(raw, 4),
                geometry_score=round(geometry, 4),
                detection_confidence=round(detection_confidence, 4),
                metric_confidence=round(metric_confidence, 4),
                reference_face_count=total_reference_faces,
                output_face_count=len(output_faces),
                selected_reference_index=reference_index,
                selected_output_index=output_face_index,
                output_face_box=_normalized_face_box(output_face, output_image.shape),
                reason_codes=reason_codes,
                metadata={
                    "provider": self.provider_name,
                    "calibration_version": CALIBRATION_VERSION,
                    "ephemeral_embedding": True,
                    "embedding_persisted": False,
                },
            )
        except Exception as exc:
            return IdentityMetricResult(
                status="unavailable",
                reason_codes=["identity_metric_error"],
                metadata={
                    "provider": self.provider_name,
                    "calibration_version": CALIBRATION_VERSION,
                    "error": str(exc)[:180],
                    "embedding_persisted": False,
                },
            )

    def _unavailable(self, code: str, reference_face_count: int, output_face_count: int) -> IdentityMetricResult:
        return IdentityMetricResult(
            status="unavailable",
            reference_face_count=reference_face_count,
            output_face_count=output_face_count,
            reason_codes=[code],
            metadata={
                "provider": self.provider_name,
                "calibration_version": CALIBRATION_VERSION,
                "embedding_persisted": False,
            },
        )

    def _load(self) -> None:
        if self._detector is not None and self._recognizer is not None:
            return
        import cv2 as cv

        self._cv = cv
        self._detector = cv.FaceDetectorYN.create(
            str(self._model_path(YUNET_FILENAME)), "", (320, 320), 0.5, 0.3, 5000
        )
        self._recognizer = cv.FaceRecognizerSF.create(str(self._model_path(SFACE_FILENAME)), "")

    def _read_image(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(path)
        image = self._cv.imread(str(path))
        if image is None:
            raise ValueError(f"unreadable image: {path}")
        return image

    def _detect(self, image) -> list[Any]:
        height, width = image.shape[:2]
        self._detector.setInputSize((width, height))
        _status, faces = self._detector.detect(image)
        return [] if faces is None else [face for face in faces]

    def _select_face(self, faces: list[Any]):
        return self._select_face_with_index(faces)[1]

    def _select_face_with_index(self, faces: list[Any]) -> tuple[int, Any]:
        return max(
            enumerate(faces),
            key=lambda item: float(item[1][2] * item[1][3]) * max(0.1, float(item[1][-1])),
        )

    def _feature(self, image, face):
        return self._recognizer.feature(self._recognizer.alignCrop(image, face))

    def _model_path(self, filename: str) -> Path:
        return self.model_dir / filename


def create_default_identity_metric_provider() -> SFaceIdentityMetricProvider:
    return SFaceIdentityMetricProvider()


def _calibrate_sface_cosine(raw: float) -> float:
    points = (
        (-0.10, 0.00),
        (0.20, 0.10),
        (0.363, 0.50),
        (0.48, 0.68),
        (0.59, 0.81),
        (0.65, 0.86),
        (0.80, 0.97),
        (1.00, 1.00),
    )
    value = max(points[0][0], min(points[-1][0], float(raw)))
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            ratio = (value - x0) / max(1e-9, x1 - x0)
            return max(0.0, min(1.0, y0 + (y1 - y0) * ratio))
    return 1.0


def _geometry_similarity(reference_face: Any, output_face: Any) -> float:
    reference = _geometry_vector(reference_face)
    output = _geometry_vector(output_face)
    tolerances = (0.22, 0.28, 0.32, 0.30, 0.30)
    penalties = [min(1.0, abs(a - b) / tolerance) for a, b, tolerance in zip(reference, output, tolerances)]
    return max(0.0, min(1.0, 1.0 - sum(penalties) / len(penalties)))


def _geometry_vector(face: Any) -> tuple[float, ...]:
    points = [(float(face[index]), float(face[index + 1])) for index in range(4, 14, 2)]
    right_eye, left_eye, nose, right_mouth, left_mouth = points
    eye_distance = max(1e-6, _distance(right_eye, left_eye))
    eye_mid = _midpoint(right_eye, left_eye)
    mouth_mid = _midpoint(right_mouth, left_mouth)
    return (
        float(face[2]) / max(1e-6, float(face[3])),
        _distance(right_mouth, left_mouth) / eye_distance,
        _distance(eye_mid, nose) / eye_distance,
        _distance(nose, mouth_mid) / eye_distance,
        (nose[0] - eye_mid[0]) / eye_distance,
    )


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _midpoint(left: tuple[float, float], right: tuple[float, float]) -> tuple[float, float]:
    return ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)


def _normalized_face_box(face: Any, shape: Any) -> list[float]:
    height, width = int(shape[0]), int(shape[1])
    return [
        round(max(0.0, min(1.0, float(face[0]) / max(1, width))), 6),
        round(max(0.0, min(1.0, float(face[1]) / max(1, height))), 6),
        round(max(0.0, min(1.0, float(face[2]) / max(1, width))), 6),
        round(max(0.0, min(1.0, float(face[3]) / max(1, height))), 6),
    ]


def _configured_model_dir() -> Path:
    try:
        from app.config import settings

        return Path(settings.v3_identity_model_dir)
    except Exception:
        return Path(os.getenv("V3_IDENTITY_MODEL_DIR", "/app/models/v3_identity"))


def _metric_enabled() -> bool:
    try:
        from app.config import settings

        return bool(settings.v3_identity_metric_enabled)
    except Exception:
        return os.getenv("V3_IDENTITY_METRIC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
