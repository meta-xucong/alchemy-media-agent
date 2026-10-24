"""Curated attention projection. Never forward arbitrary executor messages."""
MESSAGES = {
    "profile_not_enabled": "请在执行节点启用对应配置，再恢复同一任务。",
    "insufficient_disk": "请释放执行节点的磁盘空间，再恢复同一任务。",
    "codex_local_acceptance_required": "请先在本地完成 Codex 能力与工具策略验收。",
    "codex_version_not_validated": "请使用已验证的本地 Codex 版本。",
    "codex_requested_user_attention": "请检查本地 Codex 的审批或输入请求，不要发起重复生成。",
    "codex_single_image_event_required": "尚未确认唯一原图，请在本地核对本次执行。",
    "codex_original_path_missing": "已完成的原图不可用，请在本地核对本次执行。",
    "output_format_mismatch": "保留原图与请求格式不符，请检查原图，不要重新生成。",
    "import_original": "请人工生成并为该任务导入一张已确认的原图。",
    "awaiting_user_submission": "请人工提交已导出的任务，再导入原图。",
    "execution_requires_reconciliation": "执行可能已经开始，请核对同一次执行，不要重复生成。",
    "codex_prior_start_requires_reconciliation": "此前的 Codex 启动需要核对，请勿新建一轮生成。",
    "codex_execution_requires_reconciliation": "Codex 执行结果不确定，请核对同一次执行。",
    "codex_turn_not_confirmed_complete": "Codex 本轮完成状态未确认，请核对同一轮执行。",
    "attempt_already_started": "本次执行已经开始，请恢复已有证据，不要再次执行。",
}


def attention_projection(remote):
    detail = remote.get("action_required_detail")
    code = detail.get("code") if isinstance(detail, dict) else None
    if not isinstance(code, str) or code not in MESSAGES:
        code = remote.get("action_required")
    if not isinstance(code, str) or code not in MESSAGES:
        return None
    return {"code": code, "message": MESSAGES[code]}
