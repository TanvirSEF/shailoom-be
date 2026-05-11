import pytest
import httpx


def test_health_check(base_url):
    """Root endpoint should return a health check response."""
    response = httpx.get(f"{base_url}/")
    assert response.status_code == 200


def test_sitemap(base_url):
    """Sitemap should be accessible."""
    response = httpx.get(f"{base_url}/sitemap.xml")
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "").lower()
