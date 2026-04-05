import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestAPIAuth:
    async def test_api_requires_bearer_token(self, raw_api_client):
        response = await raw_api_client.get("/api/status")

        assert response.status_code == 401
        assert response.json()["code"] == "auth_error"

    async def test_api_rejects_invalid_bearer_token(self, raw_api_client):
        response = await raw_api_client.get(
            "/api/status",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 403
        assert response.json()["code"] == "auth_error"
