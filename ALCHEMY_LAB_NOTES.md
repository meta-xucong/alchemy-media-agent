# Alchemy Lab Notes

This file points reviewers to the main Alchemy Lab planning documents.

Read order:

1. `docs/alchemy_lab/00_overview.md`
2. `docs/alchemy_lab/01_product_spec.md`
3. `docs/alchemy_lab/02_architecture.md`
4. `docs/alchemy_lab/03_data_contract.md`
5. `docs/alchemy_lab/04_execution_contract.md`
6. `docs/alchemy_lab/05_ui_flow.md`
7. `docs/36_AlchemyLab质量增强与智能文案层级开发文档.md`
8. `docs/37_AlchemyLab稀有风格探索器传图模块开发文档.md`
9. `docs/38_AlchemyLab智能意图导演与参考约束规划开发文档.md`
10. `ALCHEMY_LAB_DEVELOPMENT_CHECKLIST.md`
11. `ALCHEMY_LAB_ACCEPTANCE_CHECKLIST.md`

The first Lab feature is `rare-style-explorer`.

Behavior reference:

```text
https://github.com/vibeshotclub/vsc-skills/tree/main/rare-style-explorer
```

Implementation note: the current product decision is to ship the 620-entry rare-style library as an Alchemy data asset and keep a small rewritten fallback subset only for local recovery. Future Lab features should live beside, not inside, `rare-style-explorer`.

Quality note: after the MVP feature is stable, the next planned upgrade is a Lab-owned quality enhancement layer. It must improve visual finish and text-heavy compositions through LLM judgment, not by fixed poster formulas. See `docs/36_AlchemyLab质量增强与智能文案层级开发文档.md`.

Reference-image note: the planned rare-style-explorer upload module must be Lab-owned and independent. It may copy V2 upload ideas, but it must not call V2 upload endpoints or import V2 upload services at runtime. See `docs/37_AlchemyLab稀有风格探索器传图模块开发文档.md`.

Intent-director note: the next planned Lab upgrade is a unified Lab Intent Director. It must reuse the existing Lab LLM JSON planning center, run for both text-only and text-plus-reference requests, and produce editable constraints without overriding user-selected rare styles. See `docs/38_AlchemyLab智能意图导演与参考约束规划开发文档.md`.
