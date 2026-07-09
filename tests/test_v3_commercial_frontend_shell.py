import base64
from io import BytesIO
import json

from fastapi.testclient import TestClient

from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore, PersistentProjectStore
from alchemy_creative_agent_3_0.app.product_api import V3GeneratedOutputStore, V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import InMemoryProductJobStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from app import main as app_main
from app.main import app, v3_route_handlers


def _png_base64(width: int = 320, height: int = 280) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(220, 224, 230))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _create_ready_v3_upload(client: TestClient, *, role: str = "product_reference", filename: str = "reference.png") -> str:
    created_upload = client.post(
        "/api/v3/creative-agent/uploads",
        json={"filename": filename, "mime_type": "image/png", "size_bytes": 1024, "role": role},
    )
    assert created_upload.status_code == 200
    upload_payload = created_upload.json()
    stored_upload = client.put(
        upload_payload["upload_url"],
        json={"content_base64": _png_base64(), "mime_type": "image/png"},
    )
    assert stored_upload.status_code == 200
    ready_upload = client.post(f"/api/v3/creative-agent/uploads/{upload_payload['asset_id']}/complete")
    assert ready_upload.status_code == 200
    assert ready_upload.json()["status"] == "ready"
    return upload_payload["asset_id"]


def test_v3_commercial_shell_is_in_desktop_product_navigation() -> None:
    client = TestClient(app)

    index = client.get("/")
    assert index.status_code == 200
    assert 'data-tab="v3"' in index.text
    assert "生图 V3.0 creative OS" in index.text
    assert index.text.find('data-tab="v3"') < index.text.find('data-tab="lab"')
    assert 'id="v3Tab"' in index.text
    assert 'id="v3HomeView"' in index.text
    assert 'id="v3WorkspaceView" class="v3-workspace-view" hidden' in index.text
    assert 'id="v3TemplateChooser"' in index.text
    assert 'id="v3TemplateCreatePanel"' in index.text
    assert 'id="v3SelectedTemplateTitle"' in index.text
    assert 'id="v3SelectedBrandMemoryBar"' in index.text
    assert 'id="v3NewProjectGoalInput"' in index.text
    assert 'id="v3NewProjectGoalHint" class="v3-field-hint"' in index.text
    assert 'id="v3ProjectList"' not in index.text
    assert 'id="v3ProjectDetailPanel"' in index.text
    assert 'id="v3ProjectArchiveBtn"' in index.text
    assert 'id="v3ProjectDeleteBtn"' in index.text
    assert 'id="v3ProjectSnapshot"' in index.text
    assert 'id="v3PersistentDisplayRegion"' in index.text
    assert 'id="v3ProjectOutputBoard"' in index.text
    assert 'id="v3UsefulReferenceBoard"' in index.text
    assert 'id="v3ProjectWorkflow"' in index.text
    assert 'id="v3StepActionRegion"' in index.text
    assert 'id="v3StepCards"' in index.text
    assert 'id="v3ProjectSubpage" class="panel flow-section v3-project-subpage" aria-label="项目功能子页面" hidden' in index.text
    assert 'id="v3SubpageTitle"' in index.text
    assert 'id="v3SubpageIntro"' in index.text
    assert 'id="v3SubpageBody"' in index.text
    assert 'id="v3CloseSubpageBtn"' in index.text
    assert 'id="v3ProjectNextActions"' in index.text
    assert 'id="v3WorkflowArtifacts"' in index.text
    assert 'id="v3BrandMemoryPanel"' in index.text
    assert 'id="v3BrandMemoryModal"' in index.text
    assert 'id="v3BrandMemoryForm"' in index.text
    assert 'id="v3TemplateGrid"' not in index.text
    assert "V3 项目工作台" in index.text
    assert "先选要做的项目类型" in index.text
    assert "项目概览" in index.text
    assert "不用选流程" in index.text
    assert "继续生成套图" in index.text
    assert "最近项目" in index.text
    assert "按项目展示最近生成的图片" in index.text
    assert "项目产物与记录" in index.text
    assert "返回项目主页" in index.text
    assert "上传商品图，一键生成套图" not in index.text
    assert "返回 V3 首页" in index.text
    assert "生成一组图片" in index.text
    assert 'id="v3CountInput"' in index.text
    assert 'id="v3CountValue"' in index.text
    assert 'data-v3-size="1024x1536"' in index.text
    assert 'data-v3-size="1536x1024"' in index.text
    assert "继续生成" in index.text
    assert "v3ClosureList" in index.text
    assert "v3WarningList" in index.text
    assert "v3VariationModeRow" in index.text
    assert 'data-v3-variation-mode="auto"' in index.text
    assert 'data-v3-variation-mode="selection_candidates"' in index.text
    assert 'data-v3-variation-mode="delivery_suite"' in index.text
    assert 'data-v3-variation-mode="creative_exploration"' in index.text
    assert 'data-v3-variation-mode="format_layout_adaptation"' in index.text
    assert "相似备选模式" in index.text
    assert "套图扩展模式" in index.text
    assert "创意探索模式" in index.text
    assert "尺寸/版式适配模式" in index.text
    assert "图片用途（可选）" not in index.text
    assert "v3EcommercePresetRow" in index.text
    assert "v3EcommerceAdvanced" in index.text
    assert "v3EcommerceFields" in index.text
    assert "one_click_product_set" in index.text
    assert 'id="v3ProgressPanel"' in index.text
    assert 'id="v3ProgressFill"' in index.text
    assert 'id="v3ProjectHistoryModal"' in index.text
    assert 'id="v3ProjectHistoryGrid"' in index.text
    assert 'id="v3ProjectHistoryOpenProjectBtn"' in index.text
    assert "V3 生图制作进度" in index.text
    assert "这次 V3 帮你完成了" not in index.text
    assert "生成后的图片会显示在这里" in index.text
    assert "V3 理解结果" not in index.text
    assert "Truth:" not in index.text
    assert "Selling point:" not in index.text

    v3_section = index.text[index.text.find('id="v3Tab"') : index.text.find('id="videoTab"')]
    assert "Provider" not in v3_section
    assert "Seed" not in v3_section
    assert "ControlNet" not in v3_section
    assert "ComfyUI" not in v3_section
    assert "IP-Adapter" not in v3_section

    v3_page = client.get("/creative-agent-v3/ecommerce")
    assert v3_page.status_code == 200
    assert v3_page.headers["cache-control"] == "no-store"
    assert 'id="v3Tab"' in v3_page.text

    h5 = client.get("/h5")
    assert h5.status_code == 200
    assert 'href="/creative-agent-v3"' not in h5.text
    assert 'data-tab="v3"' in h5.text
    assert 'id="mobileV3DeleteProjectBtn"' in h5.text
    assert 'id="v3Tab"' in h5.text
    assert 'id="mobileV3GoalInput"' in h5.text
    assert 'id="mobileV3ProjectGrid"' in h5.text
    assert 'id="mobileV3GenerateBtn"' in h5.text
    assert 'id="mobileV3ReferenceInput"' in h5.text
    assert 'class="v3-mobile-upload-list is-empty"' in h5.text
    assert 'id="mobileV3ShowFullPromptBtn"' in h5.text
    assert 'id="mobileV3FullPromptDialog"' in h5.text
    assert 'data-mobile-open="v3-compose"' in h5.text
    assert 'data-mobile-v3-mode="auto"' in h5.text
    assert 'data-mobile-v3-size="1024x1536"' in h5.text
    assert "v3-link-tab" in h5.text
    assert "V3 creative OS" in h5.text
    assert h5.text.find("v3-link-tab") < h5.text.find("lab-tab")


def test_v3_frontend_assets_use_v3_namespace_and_card_module_styles() -> None:
    client = TestClient(app)

    styles = client.get("/static/styles.css")
    mobile_styles = client.get("/mobile-static/mobile.css")
    script = client.get("/static/app.js")

    assert styles.status_code == 200
    assert ".v3-scenario-grid" in styles.text
    assert ".v3-scenario-card" in styles.text
    assert ".v3-home-view" in styles.text
    assert ".v3-image-history-panel" in styles.text
    assert ".v3-history-image-card" in styles.text
    assert ".v3-history-preview" in styles.text
    assert ".v3-history-project-card" in styles.text
    assert ".v3-history-project-preview" in styles.text
    assert ".v3-history-stack" in styles.text
    assert "grid-template-columns: repeat(6, minmax(0, 1fr))" in styles.text
    assert ".v3-project-history-modal" in styles.text
    assert ".v3-project-history-grid" in styles.text
    assert ".v3-project-history-image-card" in styles.text
    assert "z-index: 220" in styles.text
    assert ".v3-project-list" in styles.text
    assert ".v3-project-card" in styles.text
    assert "height: 382px" in styles.text
    assert "aspect-ratio: 1 / 1" in styles.text
    assert ".v3-project-card-top" in styles.text
    assert ".v3-project-thumb-wrap" in styles.text
    assert ".v3-project-goal-slot" in styles.text
    assert "v3-project-goal-slot" in script.text
    assert "function v3OutputStrictThumbImageUrl" in script.text
    assert 'Array.from({ length: stackCount }, () => "<span></span>").join("")' in script.text
    assert "imageCandidates: [thumbUrl].filter(Boolean)" in script.text
    assert "post_generation_review" in script.text
    assert "v3PostGenerationReviewLines" in script.text
    assert "高级查看：质量复检" in script.text
    assert ".v3-field-title-row" in styles.text
    assert ".v3-generation-settings" in styles.text
    assert ".v3-aspect-segments" in styles.text
    assert ".v3-project-snapshot" in styles.text
    assert ".v3-project-snapshot-card" in styles.text
    assert ".v3-template-chooser" in styles.text
    assert ".v3-template-choice" in styles.text
    assert ".v3-template-create-panel" in styles.text
    assert ".v3-persistent-display-region" in styles.text
    assert ".v3-step-action-region" in styles.text
    assert ".v3-project-subpage" in styles.text
    assert "position: fixed" in styles.text
    assert ".v3-project-subpage[hidden]" in styles.text
    assert ".v3-subpage-body" in styles.text
    assert ".v3-scene-panel" in styles.text
    assert "grid-template-columns: 92px minmax(140px, 0.7fr) minmax(0, 1.3fr)" in styles.text
    assert ".v3-progress-panel" in styles.text
    assert ".v3-artifact-details" in styles.text
    assert ".v3-workflow-artifacts" in styles.text
    assert ".v3-artifact-card" in styles.text
    assert ".v3-prompt-artifact" in styles.text
    assert ".v3-review-artifact ul" in styles.text
    assert ".v3-step-cards" in styles.text
    assert ".v3-step-card" in styles.text
    assert ".v3-production-entry" in styles.text
    assert ".v3-production-context" in styles.text
    assert ".v3-project-card-actions" in styles.text
    assert ".v3-intent-details" in styles.text
    assert ".v3-project-timeline" in styles.text
    assert ".v3-project-output-board" in styles.text
    assert ".v3-useful-reference-board" in styles.text
    assert ".v3-output-actions" in styles.text
    assert ".v3-process-output-details" in styles.text
    assert ".v3-process-output-grid" in styles.text
    assert '.v3-workspace-view[data-v3-opening="true"]' in styles.text
    assert ".v3-project-output-tile.selected" in styles.text
    assert ".v3-result-card.selected" in styles.text
    assert ".v3-reference-actions" in styles.text
    assert ".v3-asset-row button" in styles.text
    assert ".v3-asset-file-copy" in styles.text
    assert ".v3-project-workflow" in styles.text
    assert ".v3-project-next-actions" in styles.text
    assert ".v3-continuation-panel" in styles.text
    assert ".v3-style-memory-status" in styles.text
    assert ".v3-selected-memory-bar" in styles.text
    assert ".v3-brand-memory-panel" in styles.text
    assert ".v3-brand-memory-modal" in styles.text
    assert "z-index: 180" in styles.text
    assert 'body[data-active-module="v3"] #providerState' in styles.text
    assert 'body[data-active-module="v3"] #sessionLabel' in styles.text
    assert '.v3-workbench[data-v3-active-scenario="ecommerce"] .v3-composer-panel' in styles.text
    assert ".v3-history-list" in styles.text
    assert ".v3-history-card" in styles.text
    assert ".v3-workspace-grid" in styles.text
    assert ".v3-result-board" in styles.text
    assert ".v3-result-preview" in styles.text
    assert ".v3-preset-row[hidden]" in styles.text
    assert ".v3-variation-mode-row" in styles.text
    assert ".v3-optional-details" in styles.text
    assert "grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))" in styles.text
    assert mobile_styles.status_code == 200
    assert ".tab.v3-link-tab" in mobile_styles.text
    assert ".module-tabs .tab.v3-link-tab" in mobile_styles.text
    assert ".v3-mobile-upload-button::before" in mobile_styles.text
    assert ".v3-mobile-upload-button input" in mobile_styles.text
    assert "inset: 0" in mobile_styles.text
    assert ".v3-mobile-upload-list.is-empty" in mobile_styles.text
    assert ".v3-mobile-upload-list.empty-v2-list::before" in mobile_styles.text
    assert ".v3-mobile-loading-layer" in mobile_styles.text
    assert "position: fixed" in mobile_styles.text
    assert "rgba(246, 243, 235, 0.34)" in mobile_styles.text
    assert ".v3-mobile-full-prompt-dialog" in mobile_styles.text
    mobile_script = client.get("/mobile-static/mobile.js")
    assert mobile_script.status_code == 200
    assert "waitForMobileV3HomePreviewImages" in mobile_script.text
    assert "markMobileV3HomePreviewImageFailed" in mobile_script.text
    assert "limit=1000" not in mobile_script.text
    assert "mobileV3ProjectFetchLimit = 80" in mobile_script.text
    assert "mobileV3ProjectPageSize = 4" in mobile_script.text
    assert "project-outputs?limit=${mobileV3ProjectPageSize}&compact=true" in mobile_script.text
    assert "/project-outputs?limit=24&compact=true" not in mobile_script.text
    assert "project_id=${encodeURIComponent(projectId)}" in mobile_script.text
    assert "mobileV3SummaryThumbs" in mobile_script.text
    assert "mobileV3DisplayOutputsForProject" in mobile_script.text
    assert "mobileV3ProcessOutputsForProject" in mobile_script.text
    assert "generateMobileV3Job" in mobile_script.text
    assert "data-mobile-v3-mode" in mobile_script.text
    assert "data-mobile-v3-size" in mobile_script.text
    assert 'list.classList.remove("empty-v2-list")' in mobile_script.text
    assert 'list.classList.toggle("is-empty"' in mobile_script.text
    assert "mobileV3VisibleProjects" in mobile_script.text
    assert "mobileV3RecentProjectGroups" in mobile_script.text
    assert "mobileV3ProjectFromOutputGroup" in mobile_script.text
    assert "syncMobileV3PromptFromProject" in mobile_script.text
    assert "openMobileV3FullPrompt" in mobile_script.text
    assert "data-mobile-v3-output-prompt" in mobile_script.text
    assert "data-mobile-v3-remove-upload" in mobile_script.text
    assert "function removeMobileV3ReferenceUpload" in mobile_script.text
    assert "async function deleteMobileV3Project" in mobile_script.text
    assert "mobileV3DeleteProjectBtn" in mobile_script.text
    assert "mobileV3State.uploadFingerprints = {}" in mobile_script.text
    assert "网络有点慢，稍后点刷新项目" in mobile_script.text

    assert script.status_code == 200
    assert "const v3ApiBase" in script.text
    assert "const v3ProjectStorageKey" in script.text
    assert "const v3HistoryStorageKey" in script.text
    assert "/api/v3/creative-agent" in script.text
    assert "v3ProjectFetchLimit = 80" in script.text
    assert "v3ProjectHomePageSize = 9" in script.text
    assert "/history?limit=24" not in script.text
    assert "function openV3Home" in script.text
    assert "function openV3ScenarioWorkspace" in script.text
    assert "async function loadV3Projects" in script.text
    assert "async function loadV3ProjectOutputs" in script.text
    assert "project_id=${encodeURIComponent(scopedProjectId)}" in script.text
    assert "/project-outputs?limit=${boundedLimit}&compact=true${scoped}${cacheBust}" in script.text
    assert "loadV3ProjectOutputs({ silent: true, force: true, limit: 18 })" in script.text
    assert "loadV3ProjectOutputs({ silent: true, force: true, limit: 80 })" in script.text
    assert "/api/lab/history?limit=1000" not in script.text
    assert "function v3RecoveredLatestVisibleProjectOutputs" in script.text
    assert "recovered_without_exact_job_match" in script.text
    assert "function v3JobHasExpectedVisibleImages" in script.text
    assert "function syncV3CurrentJobFromProjectOutputs" in script.text
    assert "function setV3PageLoading" in script.text
    assert "function waitForV3Paint" in script.text
    assert "await waitForV3Paint()" in script.text
    assert "v3-page-loading-overlay" in styles.text
    assert "v3-page-loading-active" in styles.text
    assert "rgba(247, 244, 236, 0.34)" in styles.text
    assert "waitForV3HomePreviewImages" in script.text
    assert "markV3HomePreviewImageFailed" in script.text
    assert "if (v3State.projectOpening) return;" in script.text
    assert 'data-v3-output-action="prompt"' in script.text
    assert "promptOpen = false" in script.text
    assert "promptOpen: true" in script.text
    assert "els.v3PromptInput.value = v3State.currentProject?.user_goal || v3State.currentProject?.short_summary || \"\"" in script.text
    assert "v3JobVisibleImageCount(job) >= v3ExpectedImageCountForJob(job, expectedCount)" in script.text
    assert "expectedCount: generationSettings.count" in script.text
    recover_body = script.text.split("async function recoverV3GeneratedJob", 1)[1].split("function v3JobProviderRetrySummary", 1)[0]
    assert "v3RecoveredLatestVisibleProjectOutputs" not in recover_body
    assert "recovered_without_exact_job_match" not in recover_body
    assert "if (restored && v3JobHasExpectedVisibleImages(restored, expectedCount)) return restored;" not in recover_body
    assert "if (restored?.job_id === jobId && v3JobHasExpectedVisibleImages(restored, expectedCount)) return restored;" in recover_body
    assert "syncV3CurrentJobFromProjectOutputs({ preferLatest: false })" in script.text
    assert "/project-outputs?limit=${boundedLimit}&compact=true${scoped}${cacheBust}" in script.text
    assert "imageHistory" in script.text
    assert "function v3OutputVisibleInProject" in script.text
    assert "function v3ProcessProjectImageItems" in script.text
    assert "v3State.projectProcessOutputItems = processItems" in script.text
    assert "过程记录" in script.text
    assert "v3ReviewRank" in script.text
    assert "hidden_output_ids" in script.text
    assert "这次生成的图片已从项目里移除。" in script.text
    assert "function renderV3Projects" in script.text
    assert "function handleV3AssetListClick" in script.text
    assert "function removeV3AssetFile" in script.text
    assert "data-v3-remove-upload" in script.text
    assert "function renderV3ProjectDetail" in script.text
    assert "function v3LatestProjectJobId" in script.text
    assert "function renderV3ProjectOpeningState" in script.text
    assert "v3State.projectOpening = true" in script.text
    assert 'els.v3WorkspaceView.dataset.v3Opening = "true"' in script.text
    assert "async function restoreV3LatestProjectJob" in script.text
    assert "await restoreV3LatestProjectJob(v3State.currentProject" in script.text
    assert "/jobs/${encodeURIComponent(jobId)}" in script.text
    assert "function renderV3ProjectSnapshot" in script.text
    assert "function renderV3HomeTemplateChooser" in script.text
    assert "function handleV3HomeTemplateChoice" in script.text
    assert "function renderV3SelectedBrandMemoryBar" in script.text
    assert "function handleV3SelectedBrandMemoryBarClick" in script.text
    assert "function v3BrandMemoryStatus" in script.text
    assert "function v3SetBrandMemoryForNextProject" in script.text
    assert "selectedBrandMemory" in script.text
    assert "function renderV3StepCards" in script.text
    assert "function renderV3ProductionEntry" in script.text
    assert "v3-production-entry" in script.text
    assert "继续生成套图" in script.text
    assert "function v3ProjectSubpageCopy" in script.text
    assert "function renderV3ProjectSubpageScene" in script.text
    assert "function renderV3BriefScene" in script.text
    assert "function renderV3ReviewScene" in script.text
    assert "function renderV3SelectScene" in script.text
    assert "function renderV3ContinueScene" in script.text
    assert "function openV3ProjectSubpage" in script.text
    assert "function closeV3ProjectSubpage" in script.text
    assert 'openV3ProjectSubpage(button.dataset.v3Step || "compose")' in script.text
    assert "function archiveV3Project" in script.text
    assert "async function deleteV3Project" in script.text
    assert 'data-v3-project-action="delete_project"' in script.text
    assert "const v3ProjectHomePageSize = 9;" in script.text
    assert "function renderV3ProjectOutputBoard" in script.text
    assert "function handleV3ProjectOutputBoardClick" in script.text
    assert "async function selectV3OutputItem" in script.text
    assert "async function rejectV3OutputItem" in script.text
    assert "async function deleteV3OutputItem" in script.text
    assert "function v3LooksCorruptedText" in script.text
    assert "function v3ReadableText" in script.text
    assert "function v3ProjectDisplayTitle" in script.text
    assert "function v3ProjectDisplayGoal" in script.text
    assert "function openV3OutputLightbox" in script.text
    assert "data-v3-output-action" in script.text
    assert "data-v3-result-action" in script.text
    assert 'data-v3-result-action="delete"' in script.text
    assert "function renderV3UsefulReferences" in script.text
    assert "function v3UsefulReferenceItems" in script.text
    assert "function maybePersistV3UploadedReferences" in script.text
    assert "function handleV3ReferenceBoardClick" in script.text
    assert "function renderV3BrandMemoryPanel" in script.text
    assert "function openV3BrandMemoryProposal" in script.text
    assert "function confirmV3BrandMemoryProposal" in script.text
    assert "reuse_brand_style" in script.text
    assert "linked_brand_id: v3State.selectedBrandMemory?.brand_id" in script.text
    assert "function renderV3ProjectWorkflow" in script.text
    assert "function renderV3WorkflowArtifacts" in script.text
    assert "function v3WorkflowArtifact" in script.text
    assert "function v3PromptArtifact" in script.text
    assert "高级查看：最终提示词" in script.text
    assert "function handleV3ProjectActionClick" in script.text
    assert "open_ecommerce_template" not in script.text
    assert "function renderV3TemplateCards" not in script.text
    assert "function handleV3TemplateClick" not in script.text
    assert "template_first_create: true" in script.text
    assert "data-v3-project-action" in script.text
    assert "archive_project" in script.text
    assert "delete_project" in script.text
    assert "data-v3-reference-action" in script.text
    assert "async function createV3Project" in script.text
    assert "function loadV3History" in script.text
    assert "function renderV3History" in script.text
    assert "function renderV3HeroHistory" in script.text
    assert "function v3ProjectImageGroups" in script.text
    assert "function v3HistoryOutputVisible" in script.text
    assert "function v3OutputDeliveryState" in script.text
    assert "function v3DeliveryDisplayItems" in script.text
    assert 'v3OutputDeliveryState(item) !== "superseded"' in script.text
    assert "const finals = list.filter((item) => v3OutputDeliveryState(item) === \"final_delivery\")" in script.text
    assert "function openV3ProjectHistoryModal" in script.text
    assert "function renderV3ProjectHistoryGrid" in script.text
    assert "function handleV3ProjectHistoryGridClick" in script.text
    assert "function releaseV3ScrollLockIfNoModal" in script.text
    assert "closeV3ProjectHistoryModal({ keepBodyState: true })" not in script.text
    assert "releaseV3ScrollLockIfNoModal();" in script.text
    assert "data-v3-history-project-group" in script.text
    assert "function buildV3JobPayload" in script.text
    assert "selectedVariationMode" in script.text
    assert "function setV3VariationMode" in script.text
    assert "function inferV3VariationMode" in script.text
    assert "variation_mode: scenarioId" in script.text
    assert "effective_variation_mode" in script.text
    assert "continuation_mode: scenarioId" in script.text
    assert "variation_mode_source" in script.text
    assert "function v3CurrentGenerationSettings" in script.text
    assert "requested_image_count: generationSettings.count" in script.text
    assert "requested_image_size: generationSettings.size" in script.text
    assert 'openV3ProjectSubpage("compose");' in script.text
    assert "function v3TemplateIdForScenario" in script.text
    assert "function v3ProjectHasProductReference" in script.text
    assert "function v3SuiteSlotRequestForPreset" in script.text
    assert "commerce_profile_patch" in script.text
    assert "suite_slot_request" in script.text
    assert "async function uploadV3Files" in script.text
    assert "function v3UploadedAssetRoleForCurrentTask" in script.text
    assert "function v3LooksLikeHumanReferenceTask" in script.text
    assert "role: v3UploadedAssetRoleForCurrentTask(file)" in script.text
    assert "async function generateV3Job" in script.text
    assert "await createV3Job();" in script.text
    assert "uploadedAssets.map((asset) => asset.asset_id)" in script.text
    assert "/uploads" in script.text
    assert "/references" in script.text
    assert "/archive" in script.text
    assert "/remove" in script.text
    assert "/unselect" in script.text
    assert "/reject" in script.text
    assert "/brand-memory/proposal" in script.text
    assert "/brand-memory/confirm" in script.text
    assert "function renderV3GeneralSummary" in script.text
    assert "function renderV3EcommerceSummary" in script.text
    assert "function v3ScenarioWorkspaceCopy" in script.text
    assert "function renderV3OutcomeItems" in script.text
    assert "v3ProgressFill" in script.text
    assert "run-progress-step" in script.text
    assert "function v3PlainWarningText" in script.text
    assert "生成电商套图" in script.text
    assert "写一句需求即可生成电商图；上传商品图后会更稳地保持实物一致。" in script.text
    assert "function renderV3ClosureChecks" in script.text
    assert "require_real_images: true" in script.text
    assert "function v3OutputImageCandidates" in script.text
    assert "function v3MediaUrl" in script.text
    assert "const assets = Array.isArray(job?.asset_series)" in script.text
    assert "const candidates = Array.isArray(job?.candidates)" in script.text
    assert "function v3JobFromHistorySnapshot" not in script.text
    assert "function v3MergeHistorySnapshotIntoJob" not in script.text
    assert "已从本地历史快照恢复生成图片" not in script.text
    assert "v3-result-preview" in script.text
    assert "scenario_id: v3State.selectedScenario" not in script.text
    assert "template_id: \"general_template\"" in script.text
    assert "template_id: templateId" in script.text
    assert "commercial_v3_project_mode" in script.text
    assert "apply_memory_update: false" in script.text
    assert "frontend_reference_" not in script.text
    assert "v3SafeAssetToken" not in script.text
    assert "v3Placeholder" in script.text
    assert "Product truth lock" not in script.text
    assert "Selling point:" not in script.text
    assert "Truth:" not in script.text
    switch_v3_block = script.text[script.text.find('} else if (tabName === "v3")') : script.text.find('} else if (tabName === "account")')]
    assert "state.historyItems" not in switch_v3_block
    assert "renderV3HeroHistory()" in switch_v3_block
    assert 'renderHeroHistory([], { source: "v3" })' not in switch_v3_block
    v3_block = script.text[script.text.find("async function initV3Shell") : script.text.find("function setLabStyleLibraryOpen")]
    assert "/api/v2" not in v3_block
    assert "/api/lab" not in v3_block
    assert "seed" not in v3_block.lower()
    assert "sampler" not in v3_block.lower()
    assert "controlnet" not in v3_block.lower()


def test_v3_product_api_routes_are_mounted_for_frontend_shell(tmp_path) -> None:
    v3_route_handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    v3_route_handlers.service.job_store = InMemoryProductJobStore()
    v3_route_handlers.project_service.project_store = InMemoryProjectStore()
    client = TestClient(app)

    scenarios = client.get("/api/v3/creative-agent/scenarios")
    assert scenarios.status_code == 200
    scenario_payload = scenarios.json()
    assert scenario_payload["default_scenario_id"] == "general_creative"
    assert "general_creative" in scenario_payload["active_scenario_ids"]
    assert "ecommerce" in scenario_payload["active_scenario_ids"]
    assert "ecommerce" not in scenario_payload["placeholder_scenario_ids"]

    projects = client.get("/api/v3/creative-agent/projects?limit=5")
    assert projects.status_code == 200
    projects_payload = projects.json()
    templates = {item["template_id"]: item for item in projects_payload["templates"]}
    assert templates["general_template"]["project_can_create_jobs"] is True
    assert templates["general_template"]["metadata"]["manifest_version"] == "project_template_manifest_v1"
    assert templates["ecommerce_template"]["project_can_create_jobs"] is True
    assert templates["ecommerce_template"]["status"] == "active"
    assert templates["ecommerce_template"]["metadata"]["requires_product_reference"] is False
    assert templates["ecommerce_template"]["metadata"]["supports_text_to_image_fallback"] is True
    assert templates["photographer_template"]["project_can_create_jobs"] is False
    assert templates["photographer_template"]["status"] == "placeholder"
    assert templates["new_media_template"]["project_can_create_jobs"] is False
    assert templates["new_media_template"]["status"] == "placeholder"

    created_project = client.post(
        "/api/v3/creative-agent/projects",
        json={
            "user_goal": "帮我做一组清爽高级的夏季饮料宣传图，适合社媒封面和店铺活动页",
            "title": "夏季饮料宣传",
        },
    )
    assert created_project.status_code == 200
    project_payload = created_project.json()
    project_id = project_payload["project"]["project_id"]
    assert project_id.startswith("project_")
    assert project_payload["project"]["primary_template_id"] == "general_template"

    text_only_ecommerce = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs",
        json={"template_id": "ecommerce_template", "user_input": "做一组电商套图"},
    )
    assert text_only_ecommerce.status_code == 200
    text_only_payload = text_only_ecommerce.json()
    assert text_only_payload["status"] == "planned"
    assert text_only_payload["scenario"]["scenario_id"] == "ecommerce"
    assert text_only_payload["metadata"]["template_id"] == "ecommerce_template"
    assert text_only_payload["metadata"]["ecommerce_text_to_image_fallback"] is True
    assert text_only_payload["metadata"]["has_product_reference"] is False
    assert text_only_payload["metadata"]["scenario_parameters"]["text_to_image_fallback"] is True
    assert text_only_payload["metadata"]["scenario_parameters"]["has_product_reference"] is False
    assert text_only_payload["ecommerce"]["product_truth"]["confidence"]["uploaded_image"] == 0.0

    product_asset_id = _create_ready_v3_upload(client, role="product_reference", filename="beverage.png")
    ecommerce_job = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs",
        json={
            "template_id": "ecommerce_template",
            "user_input": "基于这张商品图生成一组电商套图",
            "uploaded_asset_ids": [product_asset_id],
            "commerce_profile_patch": {
                "product_category": "beverage",
                "target_platform": "amazon_us",
                "core_selling_points": ["summer refreshment"],
            },
            "suite_slot_request": ["main_image", "feature_image_1", "scenario_image"],
        },
    )
    assert ecommerce_job.status_code == 200
    ecommerce_payload = ecommerce_job.json()
    assert ecommerce_payload["status"] == "planned"
    assert ecommerce_payload["scenario"]["scenario_id"] == "ecommerce"
    assert ecommerce_payload["metadata"]["template_id"] == "ecommerce_template"
    assert ecommerce_payload["metadata"]["project_context_snapshot"]["template_id"] == "ecommerce_template"
    assert ecommerce_payload["ecommerce"]["image_recipes"]

    created_job = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs",
        json={
            "user_input": "先做一张清爽高级的小红书封面",
            "template_id": "general_template",
            "metadata": {"requested_image_count": 1, "requested_image_size": "1024x1024"},
        },
    )
    assert created_job.status_code == 200
    created_payload = created_job.json()
    assert created_payload["status"] == "planned"
    assert created_payload["api_namespace"] == "/api/v3/creative-agent"
    assert created_payload["scenario"]["scenario_id"] == "general_creative"
    assert created_payload["metadata"]["project_id"] == project_id
    assert created_payload["metadata"]["template_id"] == "general_template"
    assert created_payload["general_creative"]["scenario_id"] == "general_creative"
    assert created_payload["general_creative"]["closure_checks"]
    summary_text = json.dumps(created_payload["general_creative"], ensure_ascii=False).lower()
    assert "asset_role_analyzer" not in summary_text
    assert "visual_grammar_lock" not in summary_text
    assert "amazon" not in summary_text
    assert "marketplace" not in summary_text

    generated = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs/{created_payload['job_id']}/generate",
        json={"quality_mode": "standard", "sync_wait": True},
    )
    assert generated.status_code == 200
    generated_payload = generated.json()
    assert generated_payload["status"] == "generated"
    assert len(generated_payload["asset_series"]) == 1
    assert generated_payload["metadata"]["project_id"] == project_id

    selected = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs/{created_payload['job_id']}/select",
        json={"apply_memory_update": True, "selected_candidate_id": generated_payload["candidates"][0]["candidate_id"]},
    )
    assert selected.status_code == 200
    selected_payload = selected.json()
    assert selected_payload["status"] == "selected"
    assert selected_payload["selected_result"]["memory_update_applied"] is False
    assert selected_payload["metadata"]["brand_memory_auto_applied"] is False
    assert selected_payload["project"]["selected_output_refs"]
    assert selected_payload["project"]["reference_assets"]
    assert selected_payload["context"]["metadata"]["unselected_candidates_excluded"] is True
    assert selected_payload["context"]["selected_reference_assets"]

    context = client.get(f"/api/v3/creative-agent/projects/{project_id}/context")
    assert context.status_code == 200
    context_payload = context.json()
    assert context_payload["selected_output_assets"]
    assert context_payload["selected_reference_assets"]

    timeline = client.get(f"/api/v3/creative-agent/projects/{project_id}/timeline")
    assert timeline.status_code == 200
    timeline_items = timeline.json()["items"]
    assert [item["item_type"] for item in timeline_items] == [
        "project_created",
        "job_created",
        "job_created",
        "job_created",
        "job_generated",
        "visual_review",
        "candidate_selected",
    ]
    assert timeline_items[1]["metadata"]["template_id"] == "ecommerce_template"
    assert timeline_items[2]["metadata"]["template_id"] == "ecommerce_template"
    assert timeline_items[3]["metadata"]["template_id"] == "general_template"

    project_list = client.get("/api/v3/creative-agent/projects?limit=5")
    assert project_list.status_code == 200
    assert project_list.json()["projects"][0]["project_id"] == project_id

    selected_ref = selected_payload["project"]["selected_output_refs"][0]
    output_id = selected_ref["output_id"] or selected_ref["asset_id"] or selected_ref["candidate_id"] or selected_ref["output_ref_id"]
    unselected = client.post(f"/api/v3/creative-agent/projects/{project_id}/outputs/{output_id}/unselect", json={})
    assert unselected.status_code == 200
    assert unselected.json()["context"]["selected_output_assets"] == []

    rejected = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/outputs/{output_id}/reject",
        json={"plain_text": "不要这个偏暗方向", "reason_tags": ["dark"]},
    )
    assert rejected.status_code == 200
    assert "不要这个偏暗方向" in rejected.json()["context"]["negative_direction_notes"]

    style_asset_id = _create_ready_v3_upload(client, role="style_reference", filename="style-reference.png")
    reference = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/references",
        json={"asset_ref_id": style_asset_id, "source_type": "uploaded", "label": "Style reference"},
    )
    assert reference.status_code == 200
    assert reference.json()["reference"]["status"] == "active"

    feedback = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/feedback",
        json={"feedback_type": "avoid_direction", "plain_text": "避免画面过暗", "reason_tags": ["dark"]},
    )
    assert feedback.status_code == 200
    assert "避免画面过暗" in feedback.json()["context"]["negative_direction_notes"]

    proposal = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/brand-memory/proposal",
        json={"mode": "create"},
    )
    assert proposal.status_code == 200
    proposal_payload = proposal.json()
    assert proposal_payload["proposal"]["project_id"] == project_id
    assert proposal_payload["metadata"]["brand_memory_written"] is False
    assert style_asset_id in proposal_payload["proposal"]["reference_asset_ids"]

    confirmed_memory = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/brand-memory/confirm",
        json={
            "proposal_id": proposal_payload["proposal"]["proposal_id"],
            "edited_brand_name": "Clean Drink Style",
            "edited_style_summary": "Clean bright premium beverage visuals",
            "edited_keep_notes": ["bright background", "premium restraint"],
            "edited_avoid_notes": ["dark heavy mood"],
            "edited_usage_scenes": ["social cover"],
        },
    )
    assert confirmed_memory.status_code == 200
    confirmed_payload = confirmed_memory.json()
    brand_id = confirmed_payload["brand_id"]
    assert confirmed_payload["project"]["linked_brand_id"] == brand_id
    assert confirmed_payload["proposal"]["status"] == "confirmed"
    assert confirmed_payload["memory_update_applied"] is True

    reused_project = client.post(
        "/api/v3/creative-agent/projects",
        json={
            "user_goal": "Create a second image with the saved clean drink style",
            "linked_brand_id": brand_id,
        },
    )
    assert reused_project.status_code == 200
    assert reused_project.json()["project"]["linked_brand_id"] == brand_id

    removed_reference = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/references/{reference.json()['reference']['reference_id']}/remove",
        json={"plain_text": "这张参考不再用于后续生成"},
    )
    assert removed_reference.status_code == 200
    assert removed_reference.json()["reference"]["status"] == "inactive"
    assert style_asset_id not in [
        item["asset_ref_id"] for item in removed_reference.json()["context"]["selected_reference_assets"]
    ]

    archived = client.post(f"/api/v3/creative-agent/projects/{project_id}/archive", json={})
    assert archived.status_code == 200
    assert archived.json()["project"]["status"] == "archived"
    after_archive_list = client.get("/api/v3/creative-agent/projects?limit=5")
    assert after_archive_list.status_code == 200
    assert project_id not in [item["project_id"] for item in after_archive_list.json()["projects"]]


def test_v3_project_generate_endpoint_defaults_to_background(tmp_path, monkeypatch) -> None:
    v3_route_handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    v3_route_handlers.service.job_store = InMemoryProductJobStore()
    v3_route_handlers.project_service.project_store = InMemoryProjectStore()
    client = TestClient(app)

    created_project = client.post(
        "/api/v3/creative-agent/projects",
        json={"user_goal": "做一组清爽高级的夏季饮料宣传图"},
    )
    assert created_project.status_code == 200
    project_id = created_project.json()["project"]["project_id"]

    created_job = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs",
        json={"template_id": "general_template", "user_input": "先做一张干净明亮的封面图"},
    )
    assert created_job.status_code == 200
    job_id = created_job.json()["job_id"]

    background_calls: list[tuple[str, str, dict]] = []

    def fake_start_background(project_id_arg: str, job_id_arg: str, payload: dict) -> bool:
        background_calls.append((project_id_arg, job_id_arg, payload))
        return True

    monkeypatch.setattr(app_main, "_start_v3_project_generation_background", fake_start_background)
    generated = client.post(
        f"/api/v3/creative-agent/projects/{project_id}/jobs/{job_id}/generate",
        json={"quality_mode": "standard"},
    )

    assert generated.status_code == 200
    generated_payload = generated.json()
    assert generated_payload["status"] == "planned"
    assert generated_payload["metadata"]["background_generation_started"] is True
    assert generated_payload["metadata"]["background_generation_pending"] is True
    assert background_calls == [(project_id, job_id, {"quality_mode": "standard"})]


def test_v3_routes_reject_low_level_controls_and_run_ecommerce_pack() -> None:
    client = TestClient(app)

    low_level = client.post(
        "/api/v3/creative-agent/jobs",
        json={"user_input": "做一张活动图", "metadata": {"seed": 123}},
    )
    assert low_level.status_code == 400
    assert low_level.json()["detail"]["code"] == "invalid_v3_request"

    ecommerce = client.post(
        "/api/v3/creative-agent/jobs",
        json={
            "user_input": "传一张产品图，生成可直接用于电商的成熟套图",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": ["product_reference"],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        },
    )
    assert ecommerce.status_code == 200
    ecommerce_payload = ecommerce.json()
    assert ecommerce_payload["status"] == "planned"
    assert ecommerce_payload["scenario"]["scenario_id"] == "ecommerce"
    assert ecommerce_payload["scenario"]["can_create_jobs"] is True
    assert ecommerce_payload["ecommerce"]["platform"] == "amazon"
    assert ecommerce_payload["ecommerce"]["image_recipes"]
    assert ecommerce_payload["ecommerce"]["export_package"]["files"]


def test_v3_upload_routes_feed_ecommerce_export_manifest(tmp_path) -> None:
    v3_route_handlers.service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads")
    v3_route_handlers.service.job_store = InMemoryProductJobStore()
    client = TestClient(app)

    created_upload = client.post(
        "/api/v3/creative-agent/uploads",
        json={"filename": "desk-lamp.png", "mime_type": "image/png", "size_bytes": 1024, "role": "product_reference"},
    )
    assert created_upload.status_code == 200
    upload_payload = created_upload.json()
    assert upload_payload["asset_id"].startswith("v3_asset_")
    assert upload_payload["upload_url"].endswith("/content")

    stored_upload = client.put(
        upload_payload["upload_url"],
        json={"content_base64": _png_base64(), "mime_type": "image/png"},
    )
    assert stored_upload.status_code == 200
    assert stored_upload.json()["status"] == "stored"

    ready_upload = client.post(f"/api/v3/creative-agent/uploads/{upload_payload['asset_id']}/complete")
    assert ready_upload.status_code == 200
    assert ready_upload.json()["status"] == "ready"

    image_content = client.get(f"/api/v3/creative-agent/uploads/{upload_payload['asset_id']}/content")
    assert image_content.status_code == 200
    assert image_content.headers["content-type"] == "image/png"

    created_job = client.post(
        "/api/v3/creative-agent/jobs",
        json={
            "user_input": "Create a direct-to-use ecommerce image set for this desk lamp",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": [upload_payload["asset_id"]],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        },
    )
    assert created_job.status_code == 200
    job_payload = created_job.json()
    assert job_payload["ecommerce"]["product_truth"]["evidence_sources"] == [f"uploaded_asset:{upload_payload['asset_id']}"]

    export = client.get(f"/api/v3/creative-agent/jobs/{job_payload['job_id']}/export")
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["package_id"]
    assert export_payload["manifest"]["uploaded_assets"][0]["stored"] is True

    download = client.get(f"/api/v3/creative-agent/jobs/{job_payload['job_id']}/export/download")
    assert download.status_code == 200
    assert download.headers["content-disposition"].endswith('.json"')
    manifest = download.json()
    assert manifest["source_asset_ids"] == [upload_payload["asset_id"]]


def test_v3_output_routes_serve_v3_owned_generated_files(tmp_path) -> None:
    old_store = app_main.v3_output_store
    store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    app_main.v3_output_store = store
    client = TestClient(app)
    try:
        record = store.save_base64_output(
            job_id="job_route_output",
            candidate_id="candidate_route_output",
            asset_id="asset_route_output",
            provider="test_provider",
            model="test-model",
            encoded_image=_png_base64(),
            mime_type="image/png",
            output_format="png",
        )

        thumbnail = client.get(record.thumbnail_url)
        preview = client.get(record.preview_url)
        download = client.get(record.download_url)
    finally:
        app_main.v3_output_store = old_store

    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/png"
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"


def test_v3_project_delete_route_removes_project_scoped_files(tmp_path) -> None:
    old_handlers = app_main.v3_route_handlers
    service = V3ProductApiService(
        job_store=InMemoryProductJobStore(),
        asset_store=V3UploadedAssetStore(storage_root=tmp_path / "v3_uploads"),
        output_store=V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs"),
    )
    project_store = PersistentProjectStore(storage_root=tmp_path / "v3_projects")
    app_main.v3_route_handlers = V3ProductRouteHandlers(service=service, project_store=project_store)
    client = TestClient(app)
    try:
        asset_id = _create_ready_v3_upload(client, role="face_reference")
        created_project = client.post(
            "/api/v3/creative-agent/projects",
            json={
                "user_goal": "Create a clean portrait project",
                "primary_template_id": "general_template",
                "uploaded_asset_ids": [asset_id],
            },
        )
        assert created_project.status_code == 200
        project_id = created_project.json()["project"]["project_id"]
        project_dir = project_store.storage_root / project_id
        assert project_dir.exists()
        project = project_store.get_project(project_id)
        assert project is not None
        project.job_ids.append("job_project_delete_route")
        project_store.save_project(project)
        record = service.output_store.save_base64_output(
            job_id="job_project_delete_route",
            candidate_id="candidate_project_delete_route",
            asset_id="asset_project_delete_route",
            provider="test_provider",
            model="test-model",
            encoded_image=_png_base64(),
            mime_type="image/png",
            output_format="png",
            metadata={"project_id": project_id},
        )
        assert service.output_store.get_output(record.output_id) is not None
        assert service.asset_store.get_upload(asset_id) is not None

        deleted = client.delete(f"/api/v3/creative-agent/projects/{project_id}")
    finally:
        app_main.v3_route_handlers = old_handlers

    assert deleted.status_code == 200
    payload = deleted.json()
    assert payload["deleted"] is True
    assert payload["deleted_outputs"] == 1
    assert payload["deleted_uploaded_assets"] == 1
    assert payload["deleted_jobs"] == 0
    assert project_store.get_project(project_id) is None
    assert not project_dir.exists()
    assert service.output_store.get_output(record.output_id) is None
    assert service.asset_store.get_upload(asset_id) is None
