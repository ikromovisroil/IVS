import bleach
from bleach.css_sanitizer import CSSSanitizer


ALLOWED_DEED_TAGS = [
    "div", "span", "b", "u", "i", "strong", "em", "br", "p",
    "table", "colgroup", "col", "tbody", "thead", "tr", "td", "th",
]
ALLOWED_DEED_ATTRS = {
    "*": ["style", "id", "class", "colspan", "rowspan"],
    "col": ["style"],
    "table": ["style", "border"],
}

ALLOWED_DEED_STYLES = [
    "text-align", "font-size", "width", "border", "border-collapse", "margin-top",
]


def sanitize_deed_body(raw_html):
    cleaner = bleach.sanitizer.Cleaner(
        tags=ALLOWED_DEED_TAGS,
        attributes=ALLOWED_DEED_ATTRS,
        css_sanitizer=CSSSanitizer(
            allowed_css_properties=ALLOWED_DEED_STYLES
        ),
        strip=True,
    )
    return cleaner.clean(raw_html)