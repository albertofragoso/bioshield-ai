import re


def parse_ingredients(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    segments = _split_top_level(text)
    result: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        _extract(segment.strip(), result, seen)
    return result


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract(segment: str, result: list[str], seen: set[str]) -> None:
    paren_start = segment.find("(")
    if paren_start == -1:
        name = _clean(segment)
        _add(name, result, seen)
        return

    name = _clean(segment[:paren_start])
    _add(name, result, seen)

    inner = _inner_content(segment, paren_start)
    for sub in _split_top_level(inner):
        _extract(sub.strip(), result, seen)


def _inner_content(text: str, start: int) -> str:
    depth = 0
    chars: list[str] = []
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
            if depth > 1:
                chars.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
            chars.append(ch)
        else:
            chars.append(ch)
    return "".join(chars)


def _clean(segment: str) -> str:
    text = re.sub(r"\s*\d+(\.\d+)?\s*%", "", segment)
    return text.strip("* \t\n")


def _add(name: str, result: list[str], seen: set[str]) -> None:
    if name and name.lower() not in seen:
        seen.add(name.lower())
        result.append(name)
