"""Text normalisation applied before any pattern matching.

A spoken explainer writes "thirty-four percent", not "34%". Without this step
the scorer and the deterministic checks measure typography rather than content:
a dose drift written in words would pass unseen, and a correctly retained figure
would read as dropped. Normalisation is applied identically to every condition,
so it cannot favour one.

Scope is deliberately narrow. Plain cardinal number words become digits and the
word "percent" becomes "%". Fractions ("six and a half"), ordinals and
approximations are left alone, because turning them into numbers would invent a
precision the speaker did not use.
"""
from __future__ import annotations

import re

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}

_WORDS = set(UNITS) | set(TENS) | set(SCALES) | {"and"}
_TOKEN = re.compile(r"[A-Za-z]+|[^A-Za-z]+")


def _value(words: list[str]) -> int | None:
    total, current, seen = 0, 0, False
    for w in words:
        if w == "and":
            continue
        if w in UNITS:
            current += UNITS[w]
            seen = True
        elif w in TENS:
            current += TENS[w]
            seen = True
        elif w == "hundred":
            current = (current or 1) * 100
            seen = True
        elif w in ("thousand", "million"):
            total += (current or 1) * SCALES[w]
            current = 0
            seen = True
        else:
            return None
    return total + current if seen else None


def words_to_numbers(text: str) -> str:
    """Replace runs of cardinal number words with their digit form."""
    out: list[str] = []
    tokens = re.findall(r"[A-Za-z]+|[^A-Za-z]+", text)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()
        if low in _WORDS and low != "and":
            run_words = [low]
            run_tokens = [tok]
            j = i + 1
            while j + 1 < len(tokens):
                sep = tokens[j]
                nxt = tokens[j + 1].lower()
                if not re.fullmatch(r"[ \-]+", sep) or nxt not in _WORDS:
                    break
                run_words.append(nxt)
                run_tokens.extend([sep, tokens[j + 1]])
                j += 2
            while run_words and run_words[-1] == "and":
                run_words.pop()
                run_tokens.pop()
                run_tokens.pop()
                j -= 2
            val = _value(run_words)
            if val is not None:
                out.append(str(val))
                i = j
                continue
        out.append(tok)
        i += 1
    return "".join(out)


_PERCENT = re.compile(r"\s*\bper ?cent\b(?!age)", re.IGNORECASE)

# Contractions are expanded so that a negation is findable as the word "not".
# Without this a detector looking for "not" silently misses "didn't", which is
# how a script that correctly states a limitation gets scored as omitting it.
# "cannot" is kept as one word, and "can't" / "can not" are folded into it, so
# that a single spelling is searchable. Everything else becomes "... not".
CONTRACTIONS = {
    "can not": "cannot", "cannot": "cannot", "can't": "cannot",
    "can\u2019t": "cannot", "won't": "will not", "won\u2019t": "will not",
    "shan't": "shall not", "ain't": "is not",
}
_CONTRACTION = re.compile(
    r"\b(?:can\s?not|can[\u2019']t|won[\u2019']t|shan[\u2019']t|ain[\u2019']t)\b"
    r"|(?<=\w)n[\u2019']t\b", re.IGNORECASE)


def _expand(m: re.Match) -> str:
    tok = re.sub(r"\s+", " ", m.group(0).lower())
    return CONTRACTIONS.get(tok, " not")


def normalise(text: str) -> str:
    if not text:
        return ""
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = _CONTRACTION.sub(_expand, text)
    text = words_to_numbers(text)
    text = _PERCENT.sub("%", text)
    return text
