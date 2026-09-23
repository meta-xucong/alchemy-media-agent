"""Regression coverage for the Alchemy-to-Veyra login entry contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESKTOP_APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE_APP_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_desktop_login_recovery_uses_login_entry_before_return_callback() -> None:
    source = DESKTOP_APP_JS.read_text(encoding="utf-8")
    login_url = _function(source, "veyraLoginUrl", "hasValidVeyraSession")

    assert 'const callback = `/_veyra/return?target=${encodeURIComponent(target)}`;' in login_url
    assert 'const login = new URL("/login", base);' in login_url
    assert 'login.searchParams.set("redirect", callback);' in login_url
    assert "return login.toString();" in login_url
    assert "return `${base}/_veyra/return?target=${encodeURIComponent(target)}`;" not in login_url


def test_mobile_login_recovery_uses_login_entry_before_return_callback() -> None:
    source = MOBILE_APP_JS.read_text(encoding="utf-8")
    login_url = _function(source, "veyraLoginUrl", "cleanVeyraTicketFromUrl")

    assert 'const callback = `/_veyra/return?target=${encodeURIComponent(target)}`;' in login_url
    assert 'const login = new URL("/login", base);' in login_url
    assert 'login.searchParams.set("redirect", callback);' in login_url
    assert "return login.toString();" in login_url
    assert "return `${base}/_veyra/return?target=${encodeURIComponent(target)}`;" not in login_url
