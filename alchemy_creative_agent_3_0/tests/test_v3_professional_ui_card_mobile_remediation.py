from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPO_ROOT / "src_skeleton" / "app" / "static"
MOBILE_ROOT = REPO_ROOT / "src_skeleton" / "app" / "mobile_static"
DOC_PATH = (
    REPO_ROOT
    / "alchemy_creative_agent_3_0"
    / "docs"
    / "visual_assets"
    / "PROFESSIONAL_MODE_V3_UI_CARD_AND_MOBILE_REMEDIATION_20260726.md"
)
FRONTEND_VERSION = "20260809-v3-terminal-delivery-cachebust"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_desktop_visual_asset_content_action_opens_character_card_without_silent_noop() -> None:
    app_js = _read(STATIC_ROOT / "app.js")
    index_html = _read(STATIC_ROOT / "index.html")

    assert 'data-v3-visual-asset-action="open-card"' in app_js
    assert "if (action === \"open-card\")" in app_js
    assert "openV3CharacterCard(id)" in app_js
    assert "没有找到这个人物资产，请刷新资产库后重试。" in app_js
    assert "els.v3CharacterCardWorkspace?.scrollIntoView" not in app_js
    assert 'id="v3CharacterCardWorkspace"' in index_html


def test_doc258_frontend_cache_bust_versions_are_unified() -> None:
    index_html = _read(STATIC_ROOT / "index.html")
    mobile_html = _read(MOBILE_ROOT / "index.html")

    assert f"/static/styles.css?v={FRONTEND_VERSION}" in index_html
    assert f"/static/app.js?v={FRONTEND_VERSION}" in index_html
    assert f"/mobile-static/mobile.css?v={FRONTEND_VERSION}" in mobile_html
    assert f"/mobile-static/mobile.js?v={FRONTEND_VERSION}" in mobile_html
    assert "20260726-visual-asset-cards" not in index_html
    assert "20260719-v3-frontend-ux-fix2" not in mobile_html
    assert "20260710-v3-reference-channels" not in mobile_html


def test_desktop_people_asset_create_is_explicit_expandable_card() -> None:
    app_js = _read(STATIC_ROOT / "app.js")
    index_html = _read(STATIC_ROOT / "index.html")

    assert 'data-v3-visual-asset-action="toggle-create-asset"' in index_html
    assert "visualAssetLibraryCreateOpen" in app_js
    assert "focusBuilder" in app_js
    assert "v3State.visualAssetLibraryCreateOpen = true" in app_js
    assert "els.v3VisualAssetCreateForm.hidden = !createOpen" in app_js


def test_mobile_v3_has_standard_professional_split_and_card_surfaces() -> None:
    mobile_html = _read(MOBILE_ROOT / "index.html")
    mobile_js = _read(MOBILE_ROOT / "mobile.js")

    assert 'data-mobile-v3-workspace="standard"' in mobile_html
    assert 'data-mobile-v3-workspace="professional"' in mobile_html
    assert 'id="mobileV3ProfessionalAssetPanel"' in mobile_html
    assert 'id="mobileV3VisualAssetLibraryPanel"' in mobile_html
    assert 'id="mobileV3VisualAssetCreatePanel"' in mobile_html
    assert 'id="mobileV3VisualAssetDetailPanel"' in mobile_html
    assert "setMobileV3WorkspaceMode" in mobile_js
    assert "function mobileV3TemplateById(templateId)" in mobile_js
    assert "mobileV3TemplateCards().find" in mobile_js
    assert 'document.querySelector("#mobileV3OpenVisualAssetLibraryBtn")?.addEventListener("click"' in mobile_js
    assert 'document.querySelector("#mobileV3CreateVisualAssetShortcutBtn")?.addEventListener("click"' in mobile_js
    assert 'card.querySelector("[data-mobile-v3-visual-asset-open]")?.addEventListener("click"' in mobile_js
    assert "mobileV3CharacterCardPreviewItems" in mobile_js
    assert "mobileV3CharacterCardPreviewGridMarkup" in mobile_js
    assert "openMobileV3CharacterCardPreview" in mobile_js
    assert 'data-mobile-v3-character-card-preview' in mobile_js
    assert '"face.left_front_25"' not in mobile_js[mobile_js.index("const mobileV3CharacterCardPreviewSlots") : mobile_js.index("function mobileV3CharacterCardPreviewItems")]
    assert '"face.right_front_25"' not in mobile_js[mobile_js.index("const mobileV3CharacterCardPreviewSlots") : mobile_js.index("function mobileV3CharacterCardPreviewItems")]
    assert "openMobileV3VisualAssetLibrary" in mobile_js
    assert "openMobileV3VisualAssetCreate" in mobile_js
    assert "openMobileV3VisualAssetDetail" in mobile_js
    assert "face_identity_status" in mobile_js
    assert "expression_set_status" in mobile_js
    assert "body_silhouette_status" in mobile_js


def test_mobile_visual_asset_detail_uses_existing_character_card_routes_not_private_runtime() -> None:
    mobile_js = _read(MOBILE_ROOT / "mobile.js")
    mobile_css = _read(MOBILE_ROOT / "mobile.css")

    assert "/character-card/prepare" in mobile_js
    assert "/character-card/activate" in mobile_js
    assert "v3-mobile-character-card-preview-grid" in mobile_css
    assert "aspect-ratio: 2 / 3" in mobile_css
    assert "openImageLightbox({" in mobile_js[mobile_js.index("function openMobileV3CharacterCardPreview") : mobile_js.index("function mobileV3VisualAssetLabel")]
    prepare = mobile_js[
        mobile_js.index("async function prepareMobileV3VisualAssetModule"):
        mobile_js.index("async function activateMobileV3VisualAssetModule")
    ]
    assert "generation_channel" not in prepare
    assert 'body.source_class = "brain_inferred"' in mobile_js
    assert "private" not in mobile_js[mobile_js.index("function prepareMobileV3VisualAssetModule") : mobile_js.index("function setMobileV3Mode")]


def test_mobile_professional_project_creation_preserves_template_and_records_workspace() -> None:
    mobile_js = _read(MOBILE_ROOT / "mobile.js")

    assert 'v3_workspace: mobileV3State.workspaceMode === "professional" ? "professional" : "standard"' in mobile_js
    assert "primary_template_id: template.template_id" in mobile_js
    assert "selected_template_id: template.template_id" in mobile_js
    assert "selected_scenario_id: mobileV3ScenarioForTemplate(template.template_id)" in mobile_js


def test_mobile_v3_project_detail_recovers_blocked_outputs_and_resets_scroll() -> None:
    mobile_js = _read(MOBILE_ROOT / "mobile.js")

    assert "function mobileV3ExpectedImageCountForJob" in mobile_js
    assert "function mobileV3RecoveredJobFromProjectOutputs" in mobile_js
    assert "requested_image_count: expectedCount" in mobile_js
    assert "missing_output_count: missingCount" in mobile_js
    assert "surface.scrollTop = 0;" in mobile_js
    assert "surface.scrollLeft = 0;" in mobile_js
    refresh_body = mobile_js[mobile_js.index("async function refreshMobileV3ProjectDetail"):mobile_js.index("function renderMobileV3ProjectOutputs")]
    assert "mobileV3RecoveredJobFromProjectOutputs(project.project_id, latestJobId, latestJob, { allowPartial: true })" in refresh_body
    recover_body = mobile_js[mobile_js.index("async function recoverMobileV3GeneratedJob"):mobile_js.index("function setMobileV3Busy")]
    assert '["blocked", "failed", "not_found"].includes(lastJob?.status)' in recover_body
    assert "const recovered = mobileV3RecoveredJobFromProjectOutputs(projectId, jobId, lastJob, { allowPartial: true });" in recover_body
    assert "return recovered;" in recover_body


def test_ui_remediation_doc_records_boundaries() -> None:
    doc = _read(DOC_PATH)

    assert "Standard Mode remains the default" in doc
    assert "Uploading a source image is not activation" in doc
    assert "must not create a second private generator" in doc
    assert "Provider routing" in doc
    assert "production gates" in doc
    assert "cache-bust" in doc
    assert "Mobile must not silently force a generation route" in doc
    assert "Public error safety contract" in doc


def test_doc258_mobile_error_and_status_helpers_are_public_safe_and_proof_aware() -> None:
    mobile_js = _read(MOBILE_ROOT / "mobile.js")

    assert "function publicSafeErrorText" in mobile_js
    assert "function containsPrivateDiagnostic" in mobile_js
    for private_token in ("job_", "mcp_handoff_", "v3_output_", "sha256", "provider", "prompt"):
        assert private_token in mobile_js
    assert 'const publicErrorFallbackMessage = "暂时无法完成，请刷新后重试。"' in mobile_js
    assert "function mobileV3CharacterCardProofVerified" in mobile_js
    assert 'String(state || "empty") === "winner_selected"' in mobile_js
    assert 'return mobileV3CharacterCardProofVerified(proofRecord) ? "已完成" : "待确认";' in mobile_js
