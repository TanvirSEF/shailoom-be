import pytest
import httpx


class TestAdminAnalytics:
    def test_sales_analytics(self, base_url, admin_headers):
        """Should return sales analytics."""
        response = httpx.get(f"{base_url}/admin/analytics/sales", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "today" in data
        assert "this_month" in data
        assert "all_time" in data

    def test_top_customers(self, base_url, admin_headers):
        """Should return top customers."""
        response = httpx.get(f"{base_url}/admin/analytics/top-customers", headers=admin_headers)
        assert response.status_code == 200

    def test_revenue_chart(self, base_url, admin_headers):
        """Should return revenue chart data."""
        response = httpx.get(f"{base_url}/admin/analytics/revenue-chart", headers=admin_headers)
        assert response.status_code == 200

    def test_low_stock(self, base_url, admin_headers):
        """Should return low stock products."""
        response = httpx.get(f"{base_url}/admin/analytics/low-stock", headers=admin_headers)
        assert response.status_code == 200


class TestAdminUsers:
    def test_get_all_users(self, base_url, admin_headers):
        """Admin should get all users."""
        response = httpx.get(f"{base_url}/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        if users:
            assert "email" in users[0]
            assert "role" in users[0]

    def test_users_without_auth(self, base_url):
        """Should reject unauthenticated user list."""
        response = httpx.get(f"{base_url}/admin/users")
        assert response.status_code == 401


class TestAdminOrders:
    def test_get_all_orders(self, base_url, admin_headers):
        """Admin should get all orders."""
        response = httpx.get(f"{base_url}/admin/orders", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestAdminCoupons:
    def test_get_coupons(self, base_url, admin_headers):
        """Admin should get all coupons."""
        response = httpx.get(f"{base_url}/admin/coupons", headers=admin_headers)
        assert response.status_code == 200


class TestAdminAuditLogs:
    def test_get_audit_logs(self, base_url, admin_headers):
        """Admin should get audit logs."""
        response = httpx.get(f"{base_url}/admin/audit-logs", headers=admin_headers)
        assert response.status_code == 200


class TestSteadfast:
    def test_get_balance(self, base_url, admin_headers):
        """Should get Steadfast balance."""
        response = httpx.get(f"{base_url}/admin/steadfast/balance", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_balance" in data
