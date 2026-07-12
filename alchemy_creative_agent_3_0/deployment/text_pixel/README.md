# V3 Text-Pixel Production Deployment Inputs

This directory defines deployment-owned schemas. It intentionally contains no
font binary and no passing certification record: release owners must supply
licensed font files, owner-consented fixture evidence, and a real deployment
OCR preflight before production delivery is allowed.

## Required deployment variables

```text
V3_TEXT_PIXEL_DELIVERY_ENABLED=false
V3_TEXT_PIXEL_DELIVERY_PRODUCTION_ENABLED=false
V3_TEXT_PIXEL_ALLOW_DEVELOPMENT_FONTS=false
V3_TEXT_PIXEL_FONT_MANIFEST_PATH=/secure/deployment/text_pixel_fonts.json
V3_TEXT_PIXEL_PRODUCTION_CERTIFICATION_JSON=<accepted certification JSON>
```

`text_pixel_fonts.json` must conform to
`production_font_manifest.schema.json`. Its order is deterministic. Each font
is checked for a real file, license evidence reference, SHA-256, locale, and
`production_approved=true`; a failed check returns a structured non-delivery
status and never substitutes a font, locale, or glyph.

## Preflight

Run this in the deployment-equivalent runtime before any flag change:

```python
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService

report = V3ProductApiService().text_pixel_delivery_runtime.production_preflight()
assert report["passed"], report
```

The OCR report distinguishes `ocr_binary_unavailable`,
`ocr_language_data_unavailable`, `ocr_invocation_failed`, and
`ocr_final_pixel_success` for `eng`, `chi_sim`, and `rus` probes.

Only after retained real Gate C/D evidence is referenced by the certification
record may a release owner change the production flags. A feature branch,
unit test, mock OCR result, or metadata-only check is not certification.
