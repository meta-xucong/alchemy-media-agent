"""Match explicit poster layout requirements to evidence in V2 catalog cases."""

from __future__ import annotations

import re

from app.schemas import PromptCase


_POSTER = re.compile(r"\b(?:poster|flyer)\b|海[报報]|招贴|傳單|传单", re.I)
_QR = r"(?:\bqr\b|二维码|二維碼)"
_QR_CLAUSE = r"[^,;.!?，。；！？\n]{0,40}"
_RESERVE = r"(?:\b(?:reserv\w*|blank|placeholder)\b|预留|預留|留白|占位|佔位)"
_QR_RESERVE = re.compile(rf"{_RESERVE}{_QR_CLAUSE}{_QR}|{_QR}{_QR_CLAUSE}{_RESERVE}", re.I)
_BLANK = r"(?:\b(?:blank|empty|placeholder)\b|空白|留白|占位|佔位)"
_BLANK_QR = re.compile(rf"{_BLANK}{_QR_CLAUSE}{_QR}|{_QR}{_QR_CLAUSE}{_BLANK}", re.I)
_LAYOUT_PATTERNS = {
    "two_columns": re.compile(r"\b(?:two|2)[ -]columns?\b|[双雙两兩二]\s*[栏欄列]", re.I),
    "three_columns": re.compile(r"\b(?:three|3)[ -]columns?\b|三\s*[栏欄列]", re.I),
    "sections": re.compile(r"\b(?:columns?|grid|table|list|sections|modular layout)\b|分[栏欄区區组組]|清[单單]|表格|网格|模[块塊]", re.I),
    "qr_space": re.compile(
        rf"{_QR_RESERVE.pattern}|{_QR}{_QR_CLAUSE}(?:\b(?:space|area|region)\b|区域|區域)",
        re.I,
    ),
}
_COPY_GROUPS = (
    r"\b(?:headline|title)\b|[标標][题題]",
    r"\b(?:price|offer|discount)\b|价格|價格|原价|原價|优惠|優惠",
    r"\b(?:schedule|dates?|agenda)\b|日期|[时時]间|日程",
    r"\b(?:curriculum|details|materials|list|sections)\b|清[单單]|[课課]程[资資]料|[课課]程[内內]容|[课課]程大[纲綱]|[课課]程安[排]",
    r"\b(?:cta|register|registration|contact|qr)\b|[报報]名|[联聯]系|[扫掃][码碼]|二维码|二維碼",
)
_CASE_TEXT_LAYOUT = re.compile(
    r"\b(?:multi[- ](?:column|section)|two[- ]column|three[- ]column|modular layout|"
    r"(?:text|copy|information|price|schedule|course|menu|agenda)[ -]+(?:grid|panels|sections|table|list|columns)|"
    r"(?:grid|panels|sections|columns) (?:for|of) (?:text|copy|information|prices|content))\b|"
    r"[双雙多]\s*[栏欄列]|(?:文案|信息|文字|课程|課程|价格|價格|菜单|菜單)(?:分区|分區|清单|清單|表格|模块|模塊)|分区排版|分區排版",
    re.I,
)
_NEGATED_LAYOUT_PREFIX = re.compile(
    r"(?:\b(?:no|without|avoid|omit|do not|don't)\s+(?:(?:use|using|add|include|reserve|columns?|or|a|any|two|three|2|3)[ -]+)*"
    r"|(?:不要|无需|無需|不用|不必|避免|禁止)\s*(?:使用|加入|添加|设置|設置|保留|预留|預留|[双雙两兩二三])?\s*)$",
    re.I,
)


def is_poster_request(brief: str) -> bool:
    return bool(_POSTER.search(brief))


def _has_positive_match(pattern: re.Pattern, text: str) -> bool:
    return any(
        not _NEGATED_LAYOUT_PREFIX.search(text[max(0, match.start() - 48):match.start()])
        for match in pattern.finditer(text)
    )


def requests_blank_poster_qr_space(brief: str) -> bool:
    return is_poster_request(brief) and _has_positive_match(_BLANK_QR, brief)


def poster_layout_requirements(brief: str) -> frozenset[str]:
    if not is_poster_request(brief):
        return frozenset()
    requirements = {kind for kind, pattern in _LAYOUT_PATTERNS.items() if _has_positive_match(pattern, brief)}
    if len(requirements & {"two_columns", "three_columns"}) > 1:
        requirements.difference_update({"two_columns", "three_columns"})
        requirements.add("sections")
    if sum(bool(re.search(group, brief, re.I)) for group in _COPY_GROUPS) >= 3:
        requirements.add("sections")
    return frozenset(requirements)


def case_supports_poster_layout(case: PromptCase, requirements: frozenset[str]) -> bool:
    if case.category != "poster":
        return False
    description = "\n".join((case.title, case.summary, case.raw_prompt))
    for kind in requirements:
        if kind == "sections":
            if not _has_positive_match(_CASE_TEXT_LAYOUT, description):
                return False
        elif not _has_positive_match(_LAYOUT_PATTERNS[kind], description):
            return False
    return True
