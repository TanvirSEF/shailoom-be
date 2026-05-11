import pytest
import httpx


class TestUserProfile:
    def test_get_profile_authenticated(self, base_url, admin_headers):
        """Authenticated user should get profile."""
        response = httpx.get(f"{base_url}/users/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "email" in data

    def test_get_profile_unauthenticated(self, base_url):
        """Unauthenticated request should fail."""
        response = httpx.get(f"{base_url}/users/me")
        assert response.status_code == 401

    def test_get_addresses(self, base_url, admin_headers):
        """Should get user addresses."""
        response = httpx.get(f"{base_url}/users/me/addresses", headers=admin_headers)
        assert response.status_code == 200


class TestOrderEndpoints:
    def test_validate_coupon_missing(self, base_url):
        """Should handle missing coupon code."""
        response = httpx.get(f"{base_url}/orders/validate-coupon")
        assert response.status_code in [400, 422]

    def test_validate_invalid_coupon(self, base_url):
        """Should reject invalid coupon."""
        response = httpx.get(
            f"{base_url}/orders/validate-coupon",
            params={"code": "INVALID_CODE_12345"},
        )
        assert response.status_code in [400, 404, 422]

    def test_track_order_invalid_id(self, base_url):
        """Should handle invalid tracking ID."""
        response = httpx.get(f"{base_url}/orders/track/INVALID_ID")
        assert response.status_code == 404

    def test_my_orders_authenticated(self, base_url, admin_headers):
        """Authenticated user should see orders."""
        response = httpx.get(f"{base_url}/orders/my-orders", headers=admin_headers)
        assert response.status_code == 200

    def test_my_orders_unauthenticated(self, base_url):
        """Unauthenticated request should fail."""
        response = httpx.get(f"{base_url}/orders/my-orders")
        assert response.status_code == 401
