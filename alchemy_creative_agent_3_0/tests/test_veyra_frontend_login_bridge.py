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


def test_v2_deep_link_intent_survives_desktop_login_round_trip() -> None:
    source = DESKTOP_APP_JS.read_text(encoding="utf-8")
    route_reader = _function(source, "initialModuleRoute", "initialV3ScenarioFromPath")
    login_persistence = _function(source, "persistPendingModuleRouteForLogin", "handleVeyraUnauthorized")

    assert 'const pendingModuleRouteStorageKey = "alchemy_pending_module_route_v1";' in source
    assert "window.sessionStorage.getItem(pendingModuleRouteStorageKey)" in route_reader
    assert "window.sessionStorage.removeItem(pendingModuleRouteStorageKey)" in source
    assert 'window.sessionStorage.setItem(pendingModuleRouteStorageKey, "v2")' in login_persistence
    assert 'const directRoute = normalizeModuleRouteToken(params.get("module") || params.get("tab") || window.location.hash);' in route_reader


def test_mobile_applies_v2_route_only_after_ticket_and_session_cookie_are_ready() -> None:
    source = MOBILE_APP_JS.read_text(encoding="utf-8")
    ticket_exchange = source.index("await handleVeyraTicketFromUrl();")
    session_cookie_sync = source.index("await syncVeyraSessionCookie();")
    route_restore = source.index("restoreInitialModuleRoute();", session_cookie_sync)

    assert ticket_exchange < session_cookie_sync < route_restore
    assert "window.sessionStorage.getItem(pendingModuleRouteStorageKey)" in source
    assert 'window.sessionStorage.setItem(pendingModuleRouteStorageKey, "v2")' in source
