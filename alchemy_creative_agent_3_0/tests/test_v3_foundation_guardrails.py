from pathlib import Path


V3_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = V3_ROOT / "app"
DOCS_ROOT = V3_ROOT / "docs"


FORBIDDEN_IMPORT_PREFIXES = (
    "custom_media_agent_2_0",
    "src_skeleton.app",
)

FORBIDDEN_RUNTIME_TOKENS = (
    "ImagePromptPlan",
    "prompt_transform",
    "user_variables",
)


def _v3_app_python_files() -> list[Path]:
    if not APP_ROOT.exists():
        return []
    return sorted(APP_ROOT.rglob("*.py"))


def test_v3_foundation_guardrail_document_exists() -> None:
    guardrail_doc = DOCS_ROOT / "16_V3_FOUNDATION_EXECUTION_GUARDRAILS.md"

    assert guardrail_doc.exists()
    text = guardrail_doc.read_text(encoding="utf-8")
    assert "codex/v3-foundation" in text
    assert "src_skeleton/**" in text
    assert "custom_media_agent_2_0/**" in text
    assert "No automatic merge" in text


def test_v3_runtime_does_not_import_v1_v2_modules() -> None:
    violations: list[str] = []

    for path in _v3_app_python_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if any(prefix in stripped for prefix in FORBIDDEN_IMPORT_PREFIXES):
                rel_path = path.relative_to(V3_ROOT)
                violations.append(f"{rel_path}:{line_no}: {stripped}")

    assert not violations, "V3 app imports forbidden V1/V2 modules:\n" + "\n".join(violations)


def test_v3_runtime_does_not_reuse_forbidden_v2_concepts() -> None:
    violations: list[str] = []

    for path in _v3_app_python_files():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_RUNTIME_TOKENS:
            if token in text:
                rel_path = path.relative_to(V3_ROOT)
                violations.append(f"{rel_path}: contains {token}")

    assert not violations, "V3 app reuses forbidden V2 concepts:\n" + "\n".join(violations)
