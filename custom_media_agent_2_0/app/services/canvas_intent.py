"""Conservative, product-neutral parsing of current output-canvas instructions.

This is not a general natural-language parser: ambiguous, quoted, negative and
reference/object descriptions deliberately do not authorize a canvas override.
Provider capability negotiation remains at the provider boundary.
"""
from __future__ import annotations

import math
from fractions import Fraction
import re

_EXCLUDED = re.compile(
    r"\b(?:not|no|never|without|avoid|reference|source|previous|original|example|screen|monitor|frame|object|box|bottle|table|version|time|date)\b"
    r"|不要|不是|不得|避免|参考|參考|原图|原圖|示例|物体|物體|瓶子|桌子|相框|屏幕",
    re.I,
)
_PHYSICAL = re.compile(r"\b(?:cm|mm|inches|inch|meters)\b|厘米|毫米|英寸|公分", re.I)
_RATIO = re.compile(r"(?<![A-Za-z0-9.:/\-])([1-9]\d{0,2}(?:\.\d{1,3})?)\s*[:：]\s*([1-9]\d{0,2}(?:\.\d{1,3})?)(?![\d.:])")
_PIXELS = re.compile(r"(?<![A-Za-z0-9.\-])([1-9]\d{2,4})\s*[xX×]\s*([1-9]\d{2,4})(?!\d)")


def _output_owned(text: str, start: int, end: int) -> bool:
    """Bind a numeric mention to its nearest local owner, not sentence keywords."""
    prefix = re.split(r"[,，;；。!?\n/]|\b(?:but|instead)\b|而是|改为", text[:start], flags=re.I)[-1]
    suffix = text[end:]
    # Physical units bind directly to the numeric mention, not other objects
    # elsewhere in the prompt.
    if re.match(r"\s*(?:px|pixels?|像素)\b", suffix, re.I):
        pass
    elif re.match(r"\s*(?:cm|mm|inches|inch|meters)\b|\s*(?:厘米|毫米|英寸|公分)", suffix, re.I):
        return False
    # An output/use instruction starts a new owner even after a reference ratio.
    events = list(re.finditer(
        r"\b(?:output|canvas|image|poster|portrait|photo|illustration|cover|use|using|generate|create|render|reference|source|previous|original|example|screen|monitor|object|box|bottle|table|version|time|date|not|no|never|without|avoid)\b"
        r"|画布|畫布|输出|輸出|图片|圖片|图像|圖像|海报|海報|封面|使用|生成|参考|參考|原图|原圖|示例|物体|物體|瓶子|桌子|相框|屏幕|不要|不是|不得|避免", prefix, re.I))
    reference = negative = object_owned = False
    for event in events:
        token = event.group(0).lower()
        if token in {'reference', 'source', 'previous', 'original', 'example', '参考', '參考', '原图', '原圖', '示例'}:
            reference = True
        elif token in {'not', 'no', 'never', 'without', 'avoid', '不要', '不是', '不得', '避免'}:
            negative = True
        elif token in {'output', 'use', 'using', 'generate', 'create', 'render', '输出', '輸出', '使用', '生成'}:
            # An explicit new output directive can supersede reference ownership,
            # but cannot erase negation governing its own predicate.
            reference = object_owned = False
        elif token in {'screen', 'monitor', 'object', 'box', 'bottle', 'table', 'version', 'time', 'date', '物体', '物體', '瓶子', '桌子', '相框', '屏幕'}:
            object_owned = True
        else:
            # Image/portrait nouns and intervening adjectives are not a new
            # instruction. In particular they never erase source or negation.
            object_owned = False
    if reference or negative or object_owned:
        return False
    # Postpositive source ownership: "16:9 reference image". A normal
    # "16:9 image with a bottle" is output-owned, because image comes first.
    tail = re.match(r"\s*(?:reference|source|object|box|bottle|table)\b|\s*(?:参考|參考|物体|瓶子)", suffix, re.I)
    return not bool(tail)


def resolve_prompt_canvas(prompt: str) -> str | None:
    """Return an unambiguous affirmative canvas ratio or exact pixel size."""
    raw = str(prompt or '')

    def quoted_value(match: re.Match) -> str:
        value = match.group(0)[1:-1].strip()
        numeric = _RATIO.fullmatch(value) or _PIXELS.fullmatch(value)
        labeled = re.search(
            r"(?:aspect\s+ratio|(?:output|canvas|image)\s+(?:aspect\s+ratio|ratio|size|dimensions)|输出比例|輸出比例|输出尺寸|輸出尺寸|画布尺寸|畫布尺寸|画布比例|畫布比例)"
            r"\s*(?:(?:is|of)|为|為|是|[:：=])?\s*$", raw[:match.start()], re.I)
        # Only a quoted numeric value of an explicit canvas label is evidence.
        # Quoted prose, titles and visible image text remain literal content.
        return value if numeric and labeled else ''

    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|「[^」\n]*」|`[^`\n]*`|(?<!\w)\'[^\'\n]+\'', quoted_value, raw)
    values: set[str] = set()
    for match in _RATIO.finditer(text):
        if _output_owned(text, match.start(), match.end()):
            ratio = Fraction(match[1]) / Fraction(match[2])
            values.add(f'{ratio.numerator}:{ratio.denominator}')
    for match in _PIXELS.finditer(text):
        if _output_owned(text, match.start(), match.end()):
            values.add(f'{int(match[1])}x{int(match[2])}')
    for clause in re.split(r"[\n;；。!?！？]", text):
        width = re.search(r'(?:\bwidth(?![A-Za-z])|宽度|宽)\s*[:：=]?\s*([1-9]\d{2,4})', clause, re.I)
        height = re.search(r'(?:\bheight(?![A-Za-z])|高度|高)\s*[:：=]?\s*([1-9]\d{2,4})', clause, re.I)
        if width and height:
            start, end = min(width.start(), height.start()), max(width.end(), height.end())
            if _output_owned(clause, start, end) and not _PHYSICAL.search(clause[start:end]):
                values.add(f'{int(width[1])}x{int(height[1])}')
        for match in re.finditer(r'(?<![A-Za-z0-9])A4(?![A-Za-z0-9])', clause, re.I):
            if _output_owned(clause, match.start(), match.end()):
                values.add('3392x2400' if re.search(r'landscape|横', clause, re.I) else '2400x3392')
    if len(values) == 1:
        return next(iter(values))
    pixels = [value for value in values if 'x' in value]
    if len(pixels) == 1:
        width, height = map(int, pixels[0].split('x'))
        divisor = math.gcd(width, height)
        if values == {pixels[0], f'{width // divisor}:{height // divisor}'}:
            return pixels[0]
    return None


def exact_canvas_size(value: str) -> str:
    """Choose a resolution without changing a requested ratio, not its support."""
    standard = {'1:1': '1024x1024', '2:3': '1024x1536', '3:2': '1536x1024'}
    if value in standard:
        return standard[value]
    if ':' not in value:
        return value
    width, height = map(int, value.split(':'))
    # Scale integer ratio units to multiples of16 and a useful long edge.
    scale = max(1, math.ceil(1536 / max(width, height) / 16)) * 16
    if value in {'16:9', '9:16'}:
        scale = 96
    # Ratio-only requests need a useful default area as well as edge length.
    # This is resolution selection, not a provider support assertion; explicit
    # pixel values above are returned unchanged.
    scale = max(scale, math.ceil(math.sqrt(1048576 / (width * height)) / 16) * 16)
    return f'{width * scale}x{height * scale}'


def ambiguous_canvas_text(prompt: str) -> bool:
    """Prevent the older broad orientation heuristics from reinterpreting rejected ratios."""
    return bool(_RATIO.search(prompt))


def legacy_canvas_text(prompt: str) -> str:
    """Scope legacy orientation inference to affirmative non-reference clauses."""
    return "\n".join(clause for clause in re.split(r"[\n;；。!?！？]", prompt)
                     if not _EXCLUDED.search(clause) and not _PHYSICAL.search(clause))
