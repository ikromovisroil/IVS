import re

from django import template

register = template.Library()

_ACRONYM = re.compile(r"^[A-Z]{2,4}$")


@register.filter
def rank_case(value):
    """Lavozim: faqat birinchi harf katta, qolgani kichik; qisqa bosh harfli so'zlar (ATM, IT) o'zgarmaydi."""
    parts = re.split(r"(\s+)", (value or "").strip())
    out, first = [], True
    for w in parts:
        if not w.strip():
            out.append(w)
            continue
        keep = bool(_ACRONYM.match(re.sub(r"[().,;:]", "", w)))
        word = w if keep else w.lower()
        if first:
            first = False
            if not keep:
                word = word[:1].upper() + word[1:]
        out.append(word)
    return "".join(out)
