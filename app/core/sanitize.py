"""
Input sanitization utilities to prevent XSS and injection attacks.
Strips HTML tags and normalizes user-supplied strings before storage.
"""
import re

# Match common XSS patterns: <script>, javascript:, onerror=, etc.
HTML_TAG_PATTERN = re.compile(r"<[^>]*>", re.IGNORECASE)
SCRIPT_PATTERN = re.compile(
    r"(javascript\s*:|on\w+\s*=|<\s*script|<\s*/\s*script|eval\s*\(|expression\s*\()",
    re.IGNORECASE,
)


def sanitize_string(value: str) -> str:
    """Strip HTML tags and dangerous JS patterns from a string."""
    if not isinstance(value, str):
        return value

    # Remove HTML tags
    cleaned = HTML_TAG_PATTERN.sub("", value)

    # Remove dangerous script patterns
    cleaned = SCRIPT_PATTERN.sub("", cleaned)

    # Strip leading/trailing whitespace
    return cleaned.strip()


def sanitize_dict(data: dict, fields: list[str] | None = None) -> dict:
    """Sanitize string values in a dict. If fields specified, only sanitize those."""
    sanitized = data.copy()
    for key, value in sanitized.items():
        if fields and key not in fields:
            continue
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
    return sanitized
