"""Best-effort, V2-local source-text evidence extraction.

This module is deliberately optional: V2 asset upload remains usable when the
host has no OCR engine. Callers receive a precise availability receipt rather
than silently treating an image's unread text as extracted evidence. RapidOCR
is the preferred Chinese/English backend; Tesseract remains a compatible
fallback. Raw extracted text is returned only to the V2 asset brief / private
delivery path, never appended to the provider prompt; persisted delivery audits
use hashes from ``reference_delivery`` instead.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from functools import lru_cache
from typing import Any


def extract_source_text_evidence(image: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract line-level OCR facts without making OCR a runtime dependency.

    The return receipt is safe to persist in an ``AssetBrief.image`` payload.
    It never contains extracted text itself.
    """

    rapidocr = _rapidocr_backend()
    if rapidocr is not None:
        return _extract_with_rapidocr(rapidocr, image)
    backend = _tesseract_backend()
    if backend is None:
        return [], {
            "status": "unavailable",
            "engine": "rapidocr_or_tesseract",
            "reason": "engine_not_available",
        }
    pytesseract, output_type, language = backend
    try:
        data = pytesseract.image_to_data(
            image,
            lang=language,
            config="--psm 11",
            output_type=output_type.DICT,
        )
    except Exception as exc:  # OCR failure must not make the image upload fail.
        return [], {
            "status": "failed",
            "engine": "tesseract",
            "language": language,
            "reason": type(exc).__name__,
        }
    lines = _line_evidence(data)
    return lines, {
        "status": "extracted" if lines else "no_text_detected",
        "engine": "tesseract",
        "language": language,
        "line_count": len(lines),
    }


@lru_cache(maxsize=1)
def _rapidocr_backend() -> Any | None:
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception:
        return None


def _extract_with_rapidocr(engine: Any, image: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import numpy as np

        result = engine(np.asarray(image.convert("RGB")))
        rows = result[0] if isinstance(result, tuple) else result
    except Exception as exc:
        return [], {
            "status": "failed",
            "engine": "rapidocr_onnxruntime",
            "language": "chinese_english",
            "reason": type(exc).__name__,
        }
    evidence: list[dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        text = " ".join(str(item[1] or "").split())
        try:
            confidence = float(item[2])
        except (TypeError, ValueError):
            confidence = 0.0
        if text and confidence >= 0.35:
            evidence.append({"text": text, "confidence": round(confidence, 3), "source": "local_ocr"})
    return evidence[:80], {
        "status": "extracted" if evidence else "no_text_detected",
        "engine": "rapidocr_onnxruntime",
        "language": "chinese_english",
        "line_count": len(evidence),
    }


def _tesseract_backend() -> tuple[Any, Any, str] | None:
    try:
        import pytesseract
        from pytesseract import Output

        # ``get_tesseract_version`` verifies the native executable is present,
        # not merely that the Python wrapper was installed.
        executable = _tesseract_executable()
        if not executable:
            return None
        pytesseract.pytesseract.tesseract_cmd = executable
        _configure_tessdata_prefix(executable)
        pytesseract.get_tesseract_version()
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        return None
    language = "chi_sim+eng" if {"chi_sim", "eng"}.issubset(available) else "eng" if "eng" in available else None
    if not language:
        return None
    return pytesseract, Output, language


def _tesseract_executable() -> str | None:
    configured = str(os.getenv("V2_TESSERACT_CMD") or "").strip()
    candidates = [configured, shutil.which("tesseract") or ""]
    program_files = os.getenv("ProgramFiles") or r"C:\Program Files"
    candidates.append(str(Path(program_files) / "Tesseract-OCR" / "tesseract.exe"))
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if not Path(candidate).is_absolute() else candidate
        path = Path(resolved) if resolved else None
        if path and path.is_file():
            return str(path)
    return None


def _configure_tessdata_prefix(executable: str) -> None:
    if os.getenv("TESSDATA_PREFIX"):
        return
    configured = str(os.getenv("V2_TESSDATA_PREFIX") or "").strip()
    if configured and Path(configured).is_dir():
        os.environ["TESSDATA_PREFIX"] = configured
        return
    default = Path(executable).parent / "tessdata"
    if default.is_dir():
        os.environ["TESSDATA_PREFIX"] = str(default)


def _line_evidence(data: dict[str, Any]) -> list[dict[str, Any]]:
    words = data.get("text") if isinstance(data.get("text"), list) else []
    confidences = data.get("conf") if isinstance(data.get("conf"), list) else []
    groups: dict[tuple[int, int, int, int], list[tuple[str, float]]] = {}
    for index, raw_word in enumerate(words):
        word = " ".join(str(raw_word or "").split())
        if not word:
            continue
        try:
            confidence = float(confidences[index]) / 100.0
        except (IndexError, TypeError, ValueError):
            confidence = 0.0
        if confidence < 0.35:
            continue
        key = _line_key(data, index)
        groups.setdefault(key, []).append((word, max(0.0, min(1.0, confidence))))
    result: list[dict[str, Any]] = []
    for words_with_confidence in groups.values():
        text = " ".join(word for word, _ in words_with_confidence).strip()
        if not text:
            continue
        confidence = sum(item[1] for item in words_with_confidence) / len(words_with_confidence)
        result.append({"text": text, "confidence": round(confidence, 3), "source": "local_ocr"})
    return result[:80]


def _line_key(data: dict[str, Any], index: int) -> tuple[int, int, int, int]:
    values: list[int] = []
    for name in ("block_num", "par_num", "line_num", "page_num"):
        raw = data.get(name)
        value = raw[index] if isinstance(raw, list) and index < len(raw) else 0
        try:
            values.append(int(value))
        except (TypeError, ValueError):
            values.append(0)
    return tuple(values)  # type: ignore[return-value]
