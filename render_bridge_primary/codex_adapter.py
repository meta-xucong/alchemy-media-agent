"""Pure product-neutral Codex native-default mapping; callers version their wire."""

CODEX_ADAPTER_VERSION = "codex_cli_imagegen_v1"


def codex_cli_adaptation(params: dict, reference_count: int) -> tuple[dict, dict]:
    # Codex's imagegen tool exposes only prompt, up to five local references,
    # and transparent_background. All other Alchemy provider controls are
    # deliberately normalized to the native tool/model defaults on this copy;
    # the frozen request remains untouched for a proven pre-admission API route.
    background = str(params.get("background") or "").strip().lower()
    transparent = params.get("transparent_background") is True or background == "transparent"
    wire = {}
    if transparent:
        wire["image_options"] = {"schema_version": "1", "transparent_background": True}
    adaptation = {
        "adapter": "codex_cli_imagegen_v1",
        "defaults_applied": {
            key: ("per_unit" if key == "count" else "profile" if key == "provider_hint" else "native_default")
            for key, value in params.items()
            if value is not None and key not in {"background", "transparent_background"}
        },
        "transparent_background_requested": transparent,
        "transparent_background_mapping": "codex_cli_version_gated_or_default",
        "reference_count": reference_count,
    }
    return wire, adaptation
