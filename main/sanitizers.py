import bleach
from bleach.css_sanitizer import CSSSanitizer


ALLOWED_DEED_TAGS = [
    "div", "span", "b", "u", "i", "strong", "em", "br", "p",
    "table", "colgroup", "col", "tbody", "thead", "tr", "td", "th",
    "s", "strike", "del",
    "sup", "sub",
    "code", "pre",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote",
    "ul", "ol", "li",
    "a",
    "img",
    "hr",
]

ALLOWED_DEED_ATTRS = {
    "*": ["style", "id", "class", "colspan", "rowspan"],
    "col": ["style"],
    "table": ["style", "border"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}

ALLOWED_DEED_STYLES = [
    "text-align", "font-size", "width", "border", "border-collapse", "margin-top",
    "background-color", "color", "font-weight", "font-style",
    "page-break-after", "page-break-before", "page-break-inside",
    "break-after", "break-before", "break-inside",
    "line-height", "font-family",
    "text-indent", "margin-left", "margin-right",
]

def sanitize_deed_body(raw_html):
    cleaner = bleach.sanitizer.Cleaner(
        tags=ALLOWED_DEED_TAGS,
        attributes=ALLOWED_DEED_ATTRS,
        css_sanitizer=CSSSanitizer(
            allowed_css_properties=ALLOWED_DEED_STYLES
        ),
        strip=True,
        protocols=["http", "https", "mailto"],
    )
    return cleaner.clean(raw_html)