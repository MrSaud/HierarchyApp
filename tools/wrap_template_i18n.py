#!/usr/bin/env python3
"""
Wrap plain text in Django HTML templates with {% trans "..." %} where safe.
Run from project root: python tools/wrap_template_i18n.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc_msgid(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def trans_tag(inner: str) -> str:
    return "{% trans \"" + esc_msgid(inner.strip()) + "\" %}"


def skip_inner(s: str) -> bool:
    t = s.strip()
    if not t or "{{" in t or "{%" in t:
        return True
    if "{% trans" in t or "{% blocktrans" in t:
        return True
    return False


def process(text: str) -> str:
    def repl_title(m: re.Match) -> str:
        inner = m.group(1).strip()
        if skip_inner(inner):
            return m.group(0)
        return "{% block title %}" + trans_tag(inner) + "{% endblock %}"

    text = re.sub(
        r"\{% block title %\}\s*([^%]+?)\s*\{% endblock %\}",
        repl_title,
        text,
        flags=re.DOTALL,
    )

    for tag in ("h1", "h2", "h3", "legend"):
        pat = re.compile(rf"<{tag}([^>]*)>\s*([^<]+?)\s*</{tag}>", re.IGNORECASE)

        def repl(m: re.Match, t=tag) -> str:
            attrs, inner = m.group(1), m.group(2)
            inner_s = inner.strip()
            if skip_inner(inner_s):
                return m.group(0)
            if len(inner_s) > 280:
                return m.group(0)
            return f"<{t}{attrs}>" + trans_tag(inner_s) + f"</{t}>"

        text = pat.sub(repl, text)

    def repl_label(m: re.Match) -> str:
        open_, inner = m.group(1), m.group(2)
        inner_s = inner.strip()
        if skip_inner(inner_s) or "<" in inner_s:
            return m.group(0)

    text = re.sub(
        r"(<label[^>]*>)\s*([^<]+?)\s*</label>",
        repl_label,
        text,
        flags=re.IGNORECASE,
    )

    def repl_btn(m: re.Match) -> str:
        open_, inner = m.group(1), m.group(2)
        inner_s = inner.strip()
        if skip_inner(inner_s) or "<" in inner_s:
            return m.group(0)
        return open_ + trans_tag(inner_s) + "</button>"

    text = re.sub(
        r"(<button[^>]*>)\s*([^<]+?)\s*</button>",
        repl_btn,
        text,
        flags=re.IGNORECASE,
    )

    def repl_a(m: re.Match) -> str:
        open_, inner = m.group(1), m.group(2)
        inner_s = inner.strip()
        if skip_inner(inner_s) or "<" in inner_s:
            return m.group(0)
        if len(inner_s) > 120:
            return m.group(0)
        return open_ + trans_tag(inner_s) + "</a>"

    text = re.sub(
        r"(<a\s[^>]*>)\s*([^<]+?)\s*</a>",
        repl_a,
        text,
        flags=re.IGNORECASE,
    )

    def repl_span_class(m: re.Match) -> str:
        cls, inner = m.group(1), m.group(2)
        inner_s = inner.strip()
        if skip_inner(inner_s):
            return m.group(0)
        return f'<span class="{cls}">' + trans_tag(inner_s) + "</span>"

    text = re.sub(
        r'<span class="(d365-hub-stat__label)">\s*([^<]+?)\s*</span>',
        repl_span_class,
        text,
    )

    def repl_lead(m: re.Match) -> str:
        inner = m.group(1).strip()
        if skip_inner(inner) or "<" in inner:
            return m.group(0)
        if len(inner) > 400:
            return m.group(0)
        return '<p class="d365-card__lead">' + trans_tag(inner) + "</p>"

    text = re.sub(
        r'<p class="d365-card__lead">\s*([^<]+?)\s*</p>',
        repl_lead,
        text,
    )

    return text


def main() -> int:
    paths = list(ROOT.glob("hierarchy/templates/hierarchy/**/*.html"))
    paths += list(ROOT.glob("templates/registration/*.html"))
    changed = 0
    for p in sorted(paths):
        raw = p.read_text(encoding="utf-8")
        new = process(raw)
        if new != raw:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print("wrapped", p.relative_to(ROOT))
    print("files changed:", changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
