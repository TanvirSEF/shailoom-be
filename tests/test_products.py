import pytest
import httpx


class TestGetProducts:
    def test_get_all_products(self, base_url):
        """Should return paginated products list."""
        response = httpx.get(f"{base_url}/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert "pagination" in data
        assert isinstance(data["products"], list)

    def test_pagination_structure(self, base_url):
        """Pagination should have required fields."""
        response = httpx.get(f"{base_url}/products")
        pagination = response.json()["pagination"]
        assert "total" in pagination
        assert "page" in pagination
        assert "limit" in pagination
        assert "total_pages" in pagination

    def test_filter_by_category(self, base_url):
        """Should filter products by category."""
        response = httpx.get(f"{base_url}/products", params={"category": "Three-Piece"})
        assert response.status_code == 200
        products = response.json()["products"]
        for p in products:
            assert p["category"] == "Three-Piece"

    def test_filter_by_category_saree(self, base_url):
        """Should filter products by Saree category."""
        response = httpx.get(f"{base_url}/products", params={"category": "saree"})
        assert response.status_code == 200
        products = response.json()["products"]
        for p in products:
            assert p["category"].lower() == "saree"

    def test_sort_by_price_asc(self, base_url):
        """Should sort products by price ascending."""
        response = httpx.get(f"{base_url}/products", params={"sort_by": "price_asc"})
        products = response.json()["products"]
        if len(products) >= 2:
            assert products[0]["price"] <= products[1]["price"]

    def test_sort_by_price_desc(self, base_url):
        """Should sort products by price descending."""
        response = httpx.get(f"{base_url}/products", params={"sort_by": "price_desc"})
        products = response.json()["products"]
        if len(products) >= 2:
            assert products[0]["price"] >= products[1]["price"]

    def test_filter_by_price_range(self, base_url):
        """Should filter products by price range."""
        response = httpx.get(f"{base_url}/products", params={"min_price": 1000, "max_price": 2000})
        assert response.status_code == 200
        for p in response.json()["products"]:
            assert 1000 <= p["price"] <= 2000

    def test_search_products(self, base_url):
        """Should search products by text."""
        response = httpx.get(f"{base_url}/products", params={"search": "three"})
        assert response.status_code == 200
        products = response.json()["products"]
        assert len(products) > 0
        for p in products:
            assert "three" in p["name"].lower() or "three" in p.get("description", "").lower()

    def test_empty_result(self, base_url):
        """Should return empty for nonexistent category."""
        response = httpx.get(f"{base_url}/products", params={"category": "NonexistentCategory123"})
        assert response.status_code == 200
        assert response.json()["products"] == []

    def test_product_has_required_fields(self, base_url):
        """Each product should have required fields."""
        response = httpx.get(f"{base_url}/products")
        products = response.json()["products"]
        if products:
            p = products[0]
            required_fields = ["id", "name", "price", "category", "stock", "images"]
            for field in required_fields:
                assert field in p, f"Missing field: {field}"


class TestSearchSuggestions:
    def test_suggestions_with_valid_query(self, base_url):
        """Should return search suggestions."""
        response = httpx.get(f"{base_url}/products/search/suggestions", params={"q": "three"})
        assert response.status_code == 200
        suggestions = response.json()
        assert isinstance(suggestions, list)
        if suggestions:
            assert "name" in suggestions[0]
            assert "price" in suggestions[0]

    def test_suggestions_short_query(self, base_url):
        """Should reject queries shorter than 2 chars."""
        response = httpx.get(f"{base_url}/products/search/suggestions", params={"q": "t"})
        assert response.status_code == 422


class TestSingleProduct:
    def test_get_product_detail(self, base_url):
        """Should get single product by ID."""
        products_response = httpx.get(f"{base_url}/products")
        products = products_response.json()["products"]
        if products:
            product_id = products[0]["id"]
            response = httpx.get(f"{base_url}/products/{product_id}")
            assert response.status_code == 200
            assert response.json()["id"] == str(product_id)

    def test_get_product_invalid_id(self, base_url):
        """Should return 400 for invalid product ID."""
        response = httpx.get(f"{base_url}/products/invalid_id")
        assert response.status_code == 400

    def test_get_product_not_found(self, base_url):
        """Should return 404 for nonexistent product."""
        response = httpx.get(f"{base_url}/products/000000000000000000000000")
        assert response.status_code == 404
