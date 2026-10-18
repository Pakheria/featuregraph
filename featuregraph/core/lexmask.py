"""Lexical masking shared by annotate, parsers, and dependency inference.

Matching tags or identifiers against raw text lets a template literal or a
comment forge them. Every consumer works from one of two same-length views:

    code_only(text, lang)     comments and strings blanked
    comment_only(text, lang)  only comments kept

Newlines are preserved in both, so line numbers never shift.

ponytail: template literals are masked wholesale, including ${...}
interpolations. Add interpolation-aware lexing if a consumer ever needs
tags inside templates.
"""

from __future__ import annotations

CODE = 0
STRING = 1
COMMENT = 2

_REGEX_KEYWORDS = {
    "return", "typeof", "case", "in", "of", "yield", "await", "void",
    "delete", "do", "else", "instanceof",
}

_SUFFIX_LANG = {
    ".py": "python",
    ".ts": "js", ".tsx": "js", ".js": "js", ".jsx": "js",
    ".go": "go", ".rs": "rust",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".cs": "csharp",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".php": "php", ".rb": "ruby",
    ".swift": "swift", ".dart": "dart",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
}


def lang_for_suffix(suffix: str) -> str:
    return _SUFFIX_LANG.get(suffix.lower(), "other")


def _flags(lang: str) -> dict:
    lang = (lang or "").lower()
    if lang == "python":
        return {"hash": True, "slash": False, "block": False, "triple": True,
                "templates": False, "interp": False, "regex": False, "escapes": True}
    if lang in ("ruby", "shell"):
        return {"hash": True, "slash": False, "block": False, "triple": False,
                "templates": False, "interp": False, "regex": False, "escapes": True}
    if lang == "php":
        return {"hash": True, "slash": True, "block": True, "triple": False,
                "templates": False, "interp": False, "regex": False, "escapes": True}
    # C-family (and the generic fallback): //, /* */, '...', "..."
    return {"hash": False, "slash": True, "block": True, "triple": False,
            "templates": lang in ("js", "ts", "go"),
            "interp": lang in ("js", "ts"),
            "regex": lang in ("js", "ts"),
            "escapes": lang != "go"}  # Go raw strings: backslash does not escape


def _regex_allowed(source: str, i: int) -> bool:
    """JS/TS regex literals start after an operator, delimiter, keyword, or line start."""
    j = i - 1
    while j >= 0 and source[j] in " \t":
        j -= 1
    if j < 0 or source[j] in "\r\n":
        return True
    if source[j] in "([{,;:=!&|?}":
        return True
    if source[j] == ">" and j > 0 and source[j - 1] == "=":
        return True
    k = j
    while k >= 0 and (source[k].isalnum() or source[k] in "_$"):
        k -= 1
    return source[k + 1 : j + 1] in _REGEX_KEYWORDS


# ponytail: ASI-sensitive `foo` newline `/re/` and `) /re/` still read as division;
# a real tokenizer is the upgrade if either ever matters.


# @feature [LEXMASK-01] Classify source characters
def classify(source: str, lang: str = "other") -> bytearray:
    """Per-character classes: CODE, STRING or COMMENT (same length as source)."""
    lang = (lang or "").lower()
    flags = _flags(lang)
    cls = bytearray(len(source))
    stack = [["code"]]
    i, n = 0, len(source)

    while i < n:
        ctx = stack[-1]
        kind = ctx[0]
        ch = source[i]

        if kind == "line":
            if ch == "\n":
                stack.pop()
            else:
                cls[i] = COMMENT
            i += 1
            continue

        if kind == "block":
            cls[i] = COMMENT
            if ch == "*" and i + 1 < n and source[i + 1] == "/":
                cls[i + 1] = COMMENT
                stack.pop()
                i += 2
            else:
                i += 1
            continue

        if kind == "str":
            cls[i] = STRING
            if ch == "\\" and flags["escapes"] and i + 1 < n:
                cls[i + 1] = STRING
                i += 2
            else:
                if ch == ctx[1]:
                    stack.pop()
                i += 1
            continue

        if kind == "regex":
            cls[i] = STRING
            if ch == "\\" and i + 1 < n:
                cls[i + 1] = STRING
                i += 2
            elif ch in "\r\n":
                stack.pop()  # unterminated regex: fall back to code on the next line
            elif ch == "[":
                ctx[1] = 1
                i += 1
            elif ch == "]" and ctx[1]:
                ctx[1] = 0
                i += 1
            elif ch == "/" and not ctx[1]:
                stack.pop()
                i += 1
            else:
                i += 1
            continue

        if kind == "triple":
            quote = ctx[1]
            if source.startswith(quote * 3, i):
                cls[i] = cls[i + 1] = cls[i + 2] = STRING
                stack.pop()
                i += 3
            elif ch == "\\" and i + 1 < n:
                cls[i] = cls[i + 1] = STRING
                i += 2
            else:
                cls[i] = STRING
                i += 1
            continue

        if kind == "tmpl":
            cls[i] = STRING
            if ch == "\\" and flags["escapes"] and i + 1 < n:
                cls[i + 1] = STRING
                i += 2
            elif ch == "`":
                stack.pop()
                i += 1
            elif flags["interp"] and ch == "$" and i + 1 < n and source[i + 1] == "{":
                cls[i + 1] = STRING
                stack.append(["interp", 1])
                i += 2
            else:
                i += 1
            continue

        # code (top level or inside ${...}) — transitions first
        # PHP: #[...] is an attribute, not a hash comment.
        if flags["hash"] and ch == "#" and not (
            lang == "php" and i + 1 < n and source[i + 1] == "["
        ):
            cls[i] = COMMENT
            stack.append(["line"])
            i += 1
            continue
        if flags["slash"] and ch == "/" and i + 1 < n and source[i + 1] == "/":
            cls[i] = cls[i + 1] = COMMENT
            stack.append(["line"])
            i += 2
            continue
        if flags["block"] and ch == "/" and i + 1 < n and source[i + 1] == "*":
            cls[i] = cls[i + 1] = COMMENT
            stack.append(["block"])
            i += 2
            continue
        if flags["regex"] and ch == "/" and _regex_allowed(source, i):
            cls[i] = STRING
            stack.append(["regex", 0])
            i += 1
            continue
        if ch == "'" or ch == '"':
            if flags["triple"] and source.startswith(ch * 3, i):
                cls[i] = cls[i + 1] = cls[i + 2] = STRING
                stack.append(["triple", ch])
                i += 3
            else:
                cls[i] = STRING
                stack.append(["str", ch])
                i += 1
            continue
        if flags["templates"] and ch == "`":
            cls[i] = STRING
            stack.append(["tmpl"])
            i += 1
            continue

        if kind == "interp":
            cls[i] = STRING
            if ch == "{":
                ctx[1] += 1
            elif ch == "}":
                ctx[1] -= 1
                if ctx[1] == 0:
                    stack.pop()
        i += 1

    return cls


def _view(source: str, cls: bytearray, wanted: int) -> str:
    return "".join(
        ch if (kind == wanted or ch in "\r\n") else " "
        for ch, kind in zip(source, cls)
    )


def code_only(source: str, lang: str = "other") -> str:
    return _view(source, classify(source, lang), CODE)


def comment_only(source: str, lang: str = "other") -> str:
    return _view(source, classify(source, lang), COMMENT)
