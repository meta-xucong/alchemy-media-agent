# 16 V3 Foundation Execution Guardrails

This document defines the execution guardrails for the first Alchemy Creative Agent 3.0 implementation run.

The goal is to validate end-to-end autonomous development capability while protecting V1, V2, and Alchemy Lab from accidental changes.

## 1. Branch Rule

All V3.0 Foundation implementation work must happen on a dedicated branch:

```text
codex/v3-foundation
```

Do not develop directly on `main`.

Do not auto-merge the branch after implementation. The expected delivery flow is:

```text
implement -> test -> self-audit -> commit -> push branch -> open PR -> human review -> merge
```

## 2. Allowed Change Scope

The implementation should be limited to V3-owned files:

```text
alchemy_creative_agent_3_0/app/**
alchemy_creative_agent_3_0/tests/**
alchemy_creative_agent_3_0/docs/**
```

The normal implementation path should only create or modify:

```text
alchemy_creative_agent_3_0/app/**
alchemy_creative_agent_3_0/tests/**
```

V3 docs may be edited only when a contract needs clarification for the current V3.0 Foundation task.

## 3. Protected Areas

Do not modify these areas during the V3.0 Foundation implementation unless the user explicitly approves it in a later task:

```text
src_skeleton/**
custom_media_agent_2_0/**
custom_media_agent_2_0_docs/**
docs/alchemy_lab/**
docs/prompt-transform-conjure/**
docs/14_提示词与Agent模板.md
docs/15_开发任务拆解_Backlog.md
docs/16_参考资料.md
docs/17_开发前准备与本地运行手册.md
docs/18_验收执行矩阵.md
docs/19_全量自检报告.md
docs/20_前端界面说明.md
docs/21_密钥与部署配置.md
docs/22_2.0_Agent化案例库与中枢调度方案.md
docs/23_2.0_OpenAI_Agents_SDK优先架构方案.md
docs/24_*.md
docs/25_*.md
docs/26_*.md
docs/27_*.md
docs/28_*.md
docs/29_*.md
docs/30_*.md
docs/31_*.md
docs/32_*.md
docs/33_*.md
docs/34_*.md
docs/35_*.md
docs/36_*.md
docs/37_*.md
docs/38_*.md
docs/39_*.md
docs/40_*.md
docs/41_*.md
tests/**
src_skeleton/app/static/**
src_skeleton/app/mobile_static/**
```

Existing V1, V2, and Alchemy Lab files are reference material only.

## 4. Runtime Independence Rules

V3 code must not import, call, or depend on V1/V2 runtime modules.

Forbidden runtime imports include:

```text
custom_media_agent_2_0
src_skeleton.app
src_skeleton.app.services
src_skeleton.app.providers
```

Forbidden reused V2 concepts include:

```text
ImagePromptPlan
prompt_transform
user_variables
```

If a V2 behavior is useful, copy the minimal idea into `alchemy_creative_agent_3_0/app/`, rename it into V3 terminology, adapt it, and test it as V3-owned code.

## 5. Test Commands

Run V3 tests explicitly:

```bash
python -m pytest alchemy_creative_agent_3_0/tests
```

Run legacy tests to check that V1/V2 and existing app behavior were not broken:

```bash
python -m pytest tests
```

Run syntax checks for the V3 app:

```bash
python -m compileall alchemy_creative_agent_3_0/app
```

If `alchemy_creative_agent_3_0/app` does not exist yet, create it during implementation before running the compile step.

## 6. Required Delivery Status

The final report must include:

```text
V3_FOUNDATION_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
APP_BOUNDARY_STATUS: PASS or FAIL
VERTICAL_AGENT_EXTENSION_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

The implementation is not accepted unless all five status lines are successful:

```text
V3_FOUNDATION_STATUS: COMPLETE
INDEPENDENCE_STATUS: PASS
APP_BOUNDARY_STATUS: PASS
VERTICAL_AGENT_EXTENSION_STATUS: PASS
TEST_STATUS: PASS
```

## 7. One-Pass Development Objective

The development run should attempt to complete the whole V3.0 Foundation phase in one controlled pass:

```text
read all referenced docs
plan implementation
implement V3-owned app skeleton
add deterministic tests
run V3 tests
run legacy tests
self-audit changed files
fix issues
repeat until clean
prepare PR-ready branch
```

Do not expand scope into V3.1 or later unless the V3.0 Foundation contracts cannot be completed without a small structural stub.

## 8. Merge Safety

No automatic merge is allowed for this first full-capability validation.

The branch may be pushed and a PR may be opened after tests pass, but merge should remain a manual human decision.
