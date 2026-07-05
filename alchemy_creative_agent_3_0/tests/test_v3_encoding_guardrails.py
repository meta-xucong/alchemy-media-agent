from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_PATHS = [
    ROOT / "app" / "llm_brain",
    ROOT / "app" / "shared_capabilities" / "visual_cluster",
    ROOT / "app" / "scenario_packs" / "ecommerce",
    ROOT / "app" / "product_api" / "service.py",
    ROOT / "app" / "project_mode",
    ROOT / "docs" / "56_V3_HUMAN_NATURAL_VARIATION_AND_IDENTITY_BALANCE_SPEC.md",
    ROOT / "docs" / "57_V3_ECOMMERCE_LIFESTYLE_COUNT_AND_WATERMARK_QA_SPEC.md",
    ROOT / "docs" / "58_V3_IDENTITY_ANCHOR_STRONG_REFERENCE_AND_SUITE_DIRECTOR_SPEC.md",
]

MOJIBAKE_MARKERS = (
    "宸",
    "鐢",
    "閫",
    "椤",
    "鍥",
    "妫",
    "绗",
    "闂",
    "濂",
    "涓",
    "瀹",
    "灏",
)


def _iter_text_files(path: Path):
    if path.is_file():
        yield path
        return
    for child in path.rglob("*"):
        if child.suffix in {".py", ".md", ".js", ".html", ".css", ".json", ".txt"}:
            yield child


def test_v3_recent_source_files_do_not_contain_question_mark_or_mojibake_text() -> None:
    offenders: list[str] = []
    for scan_path in SCAN_PATHS:
        if not scan_path.exists():
            continue
        for path in _iter_text_files(scan_path):
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), 1):
                if "???" in line or "\ufffd" in line or any(marker in line for marker in MOJIBAKE_MARKERS):
                    offenders.append(f"{path.relative_to(ROOT)}:{line_number}:{line[:120]}")
                    break

    assert not offenders, "Possible encoded Chinese corruption found:\n" + "\n".join(offenders)
