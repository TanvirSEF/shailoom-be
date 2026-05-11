import pytest
import httpx


class TestLogin:
    def test_admin_login_success(self, base_url):
        """Admin should be able to login with correct credentials."""
        response = httpx.post(
            f"{base_url}/auth/login",
            data={"username": "shailoombangladesh@gmail.com", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"

    def test_login_wrong_password(self, base_url):
        """Login should fail with wrong password."""
        response = httpx.post(
            f"{base_url}/auth/login",
            data={"username": "shailoombangladesh@gmail.com", "password": "wrongpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, base_url):
        """Login should fail for nonexistent user."""
        response = httpx.post(
            f"{base_url}/auth/login",
            data={"username": "nonexistent@test.com", "password": "anything"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 401


class TestTokenRefresh:
    def test_refresh_token_success(self, base_url):
        """Should get new access token from refresh token."""
        login_response = httpx.post(
            f"{base_url}/auth/login",
            data={"username": "shailoombangladesh@gmail.com", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = httpx.post(
            f"{base_url}/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_token_invalid(self, base_url):
        """Should fail with invalid refresh token."""
        response = httpx.post(
            f"{base_url}/auth/refresh",
            json={"refresh_token": "invalid_token_here"},
        )
        assert response.status_code == 401


class TestForgotPassword:
    def test_forgot_password_returns_success(self, base_url):
        """Should always return success (anti-enumeration)."""
        response = httpx.post(
            f"{base_url}/auth/forgot-password",
            json={"email": "shailoombangladesh@gmail.com"},
        )
        assert response.status_code == 200

    def test_forgot_password_nonexistent_email(self, base_url):
        """Should return same success for nonexistent email."""
        response = httpx.post(
            f"{base_url}/auth/forgot-password",
            json={"email": "nonexistent@test.com"},
        )
        assert response.status_code == 200


class TestAuthSecurity:
    def test_protected_route_without_token(self, base_url):
        """Should reject unauthenticated requests to protected routes."""
        response = httpx.get(f"{base_url}/users/me")
        assert response.status_code == 401

    def test_admin_route_with_invalid_token(self, base_url):
        """Should reject invalid tokens on admin routes."""
        response = httpx.get(
            f"{base_url}/admin/users",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401
