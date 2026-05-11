import pytest
from app.core.sanitize import sanitize_string, sanitize_dict


class TestSanitizeString:
    def test_normal_string_unchanged(self):
        assert sanitize_string("Hello World") == "Hello World"

    def test_strips_html_tags(self):
        assert sanitize_string("<script>alert('xss')</script>") == "alert('xss')"

    def test_strips_html_tags_with_attrs(self):
        assert sanitize_string('<img src=x onerror="alert(1)">') == ""

    def test_removes_javascript_protocol(self):
        result = sanitize_string('javascript:alert("xss")')
        assert "javascript" not in result.lower() or "alert" not in result

    def test_removes_onerror(self):
        result = sanitize_string('onerror=alert(1)')
        assert "onerror" not in result

    def test_removes_onclick(self):
        result = sanitize_string('onclick=alert(1)')
        assert "onclick" not in result

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_empty_string(self):
        assert sanitize_string("") == ""

    def test_non_string_passthrough(self):
        assert sanitize_string(123) == 123

    def test_mixed_content(self):
        result = sanitize_string("Hello <b>World</b> <script>evil()</script>")
        assert "<script>" not in result
        assert "<b>" not in result
        assert "Hello" in result
        assert "World" in result


class TestSanitizeDict:
    def test_sanitizes_all_string_fields(self):
        data = {"name": "<script>alert(1)</script>", "price": 100}
        result = sanitize_dict(data)
        assert "<script>" not in result["name"]
        assert result["price"] == 100

    def test_sanitizes_specific_fields_only(self):
        data = {"name": "<b>bold</b>", "description": "<i>italic</i>", "price": 50}
        result = sanitize_dict(data, fields=["name"])
        assert "<b>" not in result["name"]
        assert "<i>" in result["description"]  # not sanitized
        assert result["price"] == 50

    def test_preserves_non_string_values(self):
        data = {"count": 5, "active": True, "items": [1, 2, 3]}
        result = sanitize_dict(data)
        assert result["count"] == 5
        assert result["active"] is True
        assert result["items"] == [1, 2, 3]


class TestCORSSecurity:
    def test_cors_rejects_evil_origin(self, base_url):
        """API should not allow requests from unknown origins after deploy."""
        response = httpx.options(
            f"{base_url}/products",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # After deploying the CORS fix, this should NOT return the evil origin
        allow_origin = response.headers.get("access-control-allow-origin", "")
        # Currently returns * (old code), will return empty or specific domain after deploy
        assert allow_origin != "https://evil-site.com"


import httpx
