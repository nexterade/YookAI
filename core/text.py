"""Text normalization helpers used at provider/render boundaries."""

_MOJIBAKE_MARKERS = ("Ã", "Â", "â", "ð", "�")


def repair_mojibake(value: str, max_rounds: int = 3) -> str:
    """Repair common UTF-8/Latin-1 double-decoding without touching normal text.

    Only attempts a round-trip when the string contains strong mojibake markers and
    keeps the candidate when it reduces those markers. This makes the repair safe
    for normal Indonesian/English text while fixing strings such as ``Ã¢ÂÂ``.
    """
    text = str(value or "")
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text

    def score(candidate: str) -> int:
        return sum(candidate.count(marker) for marker in _MOJIBAKE_MARKERS)

    current = text
    current_score = score(current)
    for _ in range(max_rounds):
        try:
            candidate = current.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        candidate_score = score(candidate)
        if candidate_score >= current_score:
            break
        current, current_score = candidate, candidate_score
    return current
