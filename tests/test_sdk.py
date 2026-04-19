from unittest.mock import MagicMock, patch

from brainiac.sdk import BrainiacClient


def test_sdk_health_smoke():
    with patch("brainiac.sdk.httpx.Client") as client_cls:
        client = MagicMock()
        response = MagicMock()
        response.json.return_value = {"status": "ONLINE"}
        response.raise_for_status.return_value = None
        client.get.return_value = response
        client_cls.return_value = client

        sdk = BrainiacClient("http://localhost:8000")
        data = sdk.health()
        assert data["status"] == "ONLINE"
        sdk.close()
        client.close.assert_called_once()
