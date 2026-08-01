"""Tests for Wilson Eval3ngine GUI server endpoints."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.wilson_eval3ngine.gui.server import (
    _get_prompt_packages,
    _get_models,
    _get_endpoints,
    _is_localhost_endpoint,
    app,
)
from fastapi.testclient import TestClient


class TestPromptPackagesEndpoint:
    """Tests for /api/prompts/packages endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module
        
        # Save original paths
        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_prompt_packages_file = server_module.PROMPT_PACKAGES_FILE
        
        # Set up temp directories
        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.PROMPT_PACKAGES_FILE = tmp_path / "prompt_packages.json"
        
        # Create a test prompt_packages.json
        test_packages = {
            "prompt_packages": [
                {
                    "id": "test_package",
                    "name": "Test Package",
                    "prompts": ["prompt 1", "prompt 2"]
                }
            ]
        }
        (tmp_path / "prompt_packages.json").write_text(json.dumps(test_packages))
        
        yield TestClient(app)
        
        # Restore original paths
        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.PROMPT_PACKAGES_FILE = orig_prompt_packages_file

    def test_list_prompt_packages_returns_packages(self, client):
        """Test that list_prompt_packages returns the correct packages."""
        response = client.get("/api/prompts/packages")
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert len(data["packages"]) == 1
        assert data["packages"][0]["id"] == "test_package"
        assert data["packages"][0]["name"] == "Test Package"
        assert len(data["packages"][0]["prompts"]) == 2

    def test_list_prompt_packages_empty_when_no_file(self, client, tmp_path):
        """Test that empty packages are returned when file doesn't exist."""
        # Remove the prompt_packages.json
        (tmp_path / "prompt_packages.json").unlink()
        
        response = client.get("/api/prompts/packages")
        assert response.status_code == 200
        data = response.json()
        assert data["packages"] == []


class TestModelsEndpoint:
    """Tests for /api/models endpoint."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module
        
        # Save original paths
        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_endpoints_file = server_module.ENDPOINTS_FILE
        orig_models_file = server_module.MODELS_FILE
        
        # Set up temp directories
        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.ENDPOINTS_FILE = tmp_path / "endpoints.json"
        server_module.MODELS_FILE = tmp_path / "models.json"
        
        # Create test data
        endpoints = [
            {
                "id": "ep_test",
                "name": "Test Endpoint",
                "url": "http://10.133.7.211:11434",
                "provider": "ollama",
                "available": True,
            }
        ]
        models = [
            {
                "id": "test-model",
                "endpointId": "ep_test",
                "provider": "ollama",
            }
        ]
        (tmp_path / "endpoints.json").write_text(json.dumps(endpoints))
        (tmp_path / "models.json").write_text(json.dumps(models))
        
        yield TestClient(app)
        
        # Restore original paths
        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.ENDPOINTS_FILE = orig_endpoints_file
        server_module.MODELS_FILE = orig_models_file

    def test_list_models_returns_enriched_models(self, client):
        """Test that list_models returns models with endpoint info."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) == 1
        model = data["models"][0]
        assert model["id"] == "test-model"
        assert model["endpointName"] == "Test Endpoint"
        assert model["provider"] == "ollama"
        assert model["endpointAvailable"] is True


class TestKiloGatewayLogin:
    """Tests for Kilo Gateway login and endpoint persistence."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module
        
        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_endpoints_file = server_module.ENDPOINTS_FILE
        orig_models_file = server_module.MODELS_FILE
        
        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.ENDPOINTS_FILE = tmp_path / "endpoints.json"
        server_module.MODELS_FILE = tmp_path / "models.json"
        
        yield TestClient(app)
        
        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.ENDPOINTS_FILE = orig_endpoints_file
        server_module.MODELS_FILE = orig_models_file

    def test_kilo_login_creates_endpoint_on_success(self, client, tmp_path, monkeypatch):
        """Test that successful Kilo login persists a Kilo Gateway endpoint."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "kilo-model-1"},
                {"id": "kilo-model-2"},
            ]
        }
        
        async def async_get(*args, **kwargs):
            return mock_resp
        
        mock_client.get = async_get
        
        async def async_enter(self):
            return self
        
        async def async_exit(self, *args):
            pass
        
        mock_client.__aenter__ = async_enter
        mock_client.__aexit__ = async_exit
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/kilo/login", json={
            "url": "https://api.kilo.ai/api/gateway",
            "apiKey": "test-key",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["models"]) == 2
        
        # Verify endpoint was persisted
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        kilo_endpoints = [e for e in endpoints if e.get("provider") == "kilo"]
        assert len(kilo_endpoints) == 1
        assert kilo_endpoints[0]["url"] == "https://api.kilo.ai/api/gateway"
        assert kilo_endpoints[0]["available"] is True

    def test_kilo_login_does_not_duplicate_endpoint(self, client, tmp_path, monkeypatch):
        """Test that Kilo login does not duplicate existing endpoint."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "kilo-model-1"}]}
        
        async def async_get(*args, **kwargs):
            return mock_resp
        
        mock_client.get = async_get
        
        async def async_enter(self):
            return self
        
        async def async_exit(self, *args):
            pass
        
        mock_client.__aenter__ = async_enter
        mock_client.__aexit__ = async_exit
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        # Pre-create the endpoint with legacy plaintext apiKey (backward compat test)
        endpoints = [
            {
                "id": "ep_existing",
                "name": "Kilo Gateway",
                "url": "https://api.kilo.ai/api/gateway",
                "apiKey": "test-key",
                "provider": "kilo",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "available": None,
                "lastTested": None,
            }
        ]
        (tmp_path / "endpoints.json").write_text(json.dumps(endpoints))
        
        response = client.post("/api/kilo/login", json={
            "url": "https://api.kilo.ai/api/gateway",
            "apiKey": "test-key",
        })
        assert response.status_code == 200
        
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        kilo_endpoints = [e for e in endpoints if e.get("provider") == "kilo"]
        assert len(kilo_endpoints) == 1


class TestProviderLogin:
    """Tests for NVIDIA, Ollama, and Codex provider login handlers."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module
        
        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_endpoints_file = server_module.ENDPOINTS_FILE
        orig_models_file = server_module.MODELS_FILE
        
        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.ENDPOINTS_FILE = tmp_path / "endpoints.json"
        server_module.MODELS_FILE = tmp_path / "models.json"
        
        yield TestClient(app)
        
        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.ENDPOINTS_FILE = orig_endpoints_file
        server_module.MODELS_FILE = orig_models_file

    def _make_mock_http_client(self, status_code=200, json_data=None):
        """Helper to create a mock httpx.AsyncClient."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or {"data": []}
        mock_resp.headers = {}
        
        async def async_get(*args, **kwargs):
            return mock_resp
        
        mock_client.get = async_get
        
        async def async_enter(self):
            return self
        
        async def async_exit(self, *args):
            pass
        
        mock_client.__aenter__ = async_enter
        mock_client.__aexit__ = async_exit
        return mock_client

    def test_nvidia_login_creates_endpoint_on_success(self, client, tmp_path, monkeypatch):
        """Test that successful NVIDIA login persists an endpoint with provider 'nvidia'."""
        mock_client = self._make_mock_http_client(
            json_data={"data": [{"id": "nv-mistral-8x7b"}, {"id": "nv-llama-3"}]}
        )
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/nvidia/login", json={
            "url": "https://integrate.api.nvidia.com/v1",
            "apiKey": "nvapi-testkey12345678",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["models"]) == 2
        assert "NVIDIA" in data["message"]
        
        # Verify endpoint was persisted with nvidia provider
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        nvidia_endpoints = [e for e in endpoints if e.get("provider") == "nvidia"]
        assert len(nvidia_endpoints) == 1
        assert nvidia_endpoints[0]["url"] == "https://integrate.api.nvidia.com/v1"
        assert nvidia_endpoints[0]["available"] is True

    def test_nvidia_login_requires_api_key(self, client, tmp_path, monkeypatch):
        """Test that NVIDIA login fails without an API key."""
        mock_client = self._make_mock_http_client()
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/nvidia/login", json={
            "url": "https://integrate.api.nvidia.com/v1",
            "apiKey": None,
        })
        data = response.json()
        assert data["ok"] is False
        assert "API key" in data["error"]

    def test_nvidia_login_rejects_wrong_key_prefix(self, client, tmp_path, monkeypatch):
        """Test that NVIDIA login rejects keys without nvapi- prefix."""
        mock_client = self._make_mock_http_client()
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/nvidia/login", json={
            "url": "https://integrate.api.nvidia.com/v1",
            "apiKey": "sk-testkey12345678901234567890",
        })
        data = response.json()
        assert data["ok"] is False
        assert "nvapi-" in data["error"]

    def test_nvidia_login_rejects_localhost(self, client, tmp_path, monkeypatch):
        """Test that NVIDIA login rejects localhost URLs."""
        mock_client = self._make_mock_http_client()
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/nvidia/login", json={
            "url": "http://localhost:8000/v1",
            "apiKey": "nvapi-testkey12345678",
        })
        data = response.json()
        assert data["ok"] is False
        assert "Localhost" in data["error"]

    def test_ollama_login_creates_endpoint_on_success(self, client, tmp_path, monkeypatch):
        """Test that successful Ollama login persists an endpoint with provider 'ollama'."""
        mock_client = self._make_mock_http_client(
            json_data={"models": [{"name": "llama3.1"}, {"name": "phi3"}]}
        )
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/ollama/login", json={
            "url": "http://localhost:11434",
            "apiKey": None,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert len(data["models"]) == 2
        
        # Verify endpoint was persisted with ollama provider
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        ollama_endpoints = [e for e in endpoints if e.get("provider") == "ollama"]
        assert len(ollama_endpoints) == 1
        assert ollama_endpoints[0]["url"] == "http://localhost:11434"
        assert ollama_endpoints[0]["available"] is True

    def test_ollama_login_handles_connection_failure(self, client, tmp_path, monkeypatch):
        """Test that Ollama login reports failure gracefully on connection error."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.headers = {}
        mock_resp.json.return_value = {}
        
        async def async_get(*args, **kwargs):
            return mock_resp
        
        mock_client.get = async_get
        async def async_enter(self):
            return self
        async def async_exit(self, *args):
            pass
        mock_client.__aenter__ = async_enter
        mock_client.__aexit__ = async_exit
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)
        
        response = client.post("/api/ollama/login", json={
            "url": "http://localhost:11434",
            "apiKey": None,
        })
        data = response.json()
        assert data["ok"] is False

    def test_codex_login_creates_endpoint_on_success(self, client, tmp_path, monkeypatch):
        """Test that successful Codex login persists an endpoint with provider 'codex_cli'."""
        import src.wilson_eval3ngine.providers.cli_base as cli_base
        
        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/codex" if name == "codex" else None)
        
        mock_adapter = MagicMock()
        mock_adapter.detect_available.return_value = True
        mock_adapter.get_supported_models.return_value = ["codex-mini-latest", "o3-mini"]
        monkeypatch.setattr(cli_base, "CodexCLIAdapter", lambda: mock_adapter)
        
        response = client.post("/api/codex/login", json={
            "url": "cli://codex",
            "apiKey": None,
        })
        data = response.json()
        assert data["ok"] is True
        assert "Codex" in data["message"]
        assert len(data["models"]) == 2
        
        # Verify endpoint was persisted with codex_cli provider
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        codex_endpoints = [e for e in endpoints if e.get("provider") == "codex_cli"]
        assert len(codex_endpoints) == 1
        assert codex_endpoints[0]["url"] == "cli://codex"
        assert codex_endpoints[0]["available"] is True

    def test_codex_login_fails_when_cli_not_in_path(self, client, tmp_path, monkeypatch):
        """Test that Codex login fails when codex CLI is not installed."""
        monkeypatch.setattr("shutil.which", lambda name: None)
        
        response = client.post("/api/codex/login", json={
            "url": "cli://codex",
            "apiKey": None,
        })
        data = response.json()
        assert data["ok"] is False
        assert "not found" in data["error"]

    def test_codex_login_does_not_duplicate_endpoint(self, client, tmp_path, monkeypatch):
        """Test that Codex login updates existing endpoint instead of duplicating."""
        import src.wilson_eval3ngine.providers.cli_base as cli_base
        
        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/codex" if name == "codex" else None)
        
        mock_adapter = MagicMock()
        mock_adapter.detect_available.return_value = True
        mock_adapter.get_supported_models.return_value = ["codex-mini-latest"]
        monkeypatch.setattr(cli_base, "CodexCLIAdapter", lambda: mock_adapter)
        
        # Pre-create a Codex CLI endpoint
        endpoints = [
            {
                "id": "ep_existing_codex",
                "name": "Codex CLI",
                "url": "cli://codex",
                "apiKey": None,
                "provider": "codex_cli",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "available": None,
                "lastTested": None,
            }
        ]
        (tmp_path / "endpoints.json").write_text(json.dumps(endpoints))
        
        response = client.post("/api/codex/login", json={
            "url": "cli://codex",
            "apiKey": None,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        
        # Verify no duplicate was created
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        codex_endpoints = [e for e in endpoints if e.get("provider") == "codex_cli"]
        assert len(codex_endpoints) == 1
        assert codex_endpoints[0]["available"] is True


class TestReportsEndpoint:
    """Tests for /api/reports endpoint with run grouping."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module
        
        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_telemetry_file = server_module.TELEMETRY_FILE
        
        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.TELEMETRY_FILE = tmp_path / "telemetry.json"
        
        yield TestClient(app)
        
        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.TELEMETRY_FILE = orig_telemetry_file

    def test_list_reports_includes_report_runs(self, client, tmp_path):
        """Test that list_reports includes reportRuns from telemetry."""
        # Create a fake report PDF
        (tmp_path / "reports" / "test-evaluation.pdf").write_bytes(b"%PDF-1.4 fake")
        
        # Create telemetry with a report_generation run
        telemetry = [
            {
                "runId": "run-abc123",
                "type": "report_generation",
                "startedAt": "2026-07-18T10:00:00+00:00",
                "models": ["model-a", "model-b"],
                "artifacts": ["model-a-evaluation.pdf", "model-b-evaluation.pdf"],
            }
        ]
        (tmp_path / "telemetry.json").write_text(json.dumps(telemetry))
        
        response = client.get("/api/reports")
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert len(data["reports"]) == 1
        assert "reportRuns" in data
        assert len(data["reportRuns"]) == 1
        assert data["reportRuns"][0]["runId"] == "run-abc123"
        assert len(data["reportRuns"][0]["artifacts"]) == 2


class TestLocalhostEndpointValidation:
    """Tests for localhost endpoint blocking."""

    def test_rejects_localhost_http(self):
        assert _is_localhost_endpoint("http://localhost:11434") is True

    def test_rejects_localhost_https(self):
        assert _is_localhost_endpoint("https://localhost:11434") is True

    def test_rejects_127_0_0_1(self):
        assert _is_localhost_endpoint("http://127.0.0.1:11434") is True

    def test_rejects_127_0_0_1_https(self):
        assert _is_localhost_endpoint("https://127.0.0.1:11434") is True

    def test_allows_gateway(self):
        assert _is_localhost_endpoint("http://10.133.7.211:11434") is False

    def test_allows_remote(self):
        assert _is_localhost_endpoint("http://example.com:11434") is False


class TestAPIKeySecurity:
    """Tests for API key security: encryption at rest, response stripping, no leakage."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """Create a test client with temporary data directory."""
        import src.wilson_eval3ngine.gui.server as server_module

        orig_data_dir = server_module.GUI_DATA_DIR
        orig_reports_dir = server_module.REPORTS_DIR
        orig_endpoints_file = server_module.ENDPOINTS_FILE
        orig_models_file = server_module.MODELS_FILE

        server_module.GUI_DATA_DIR = tmp_path
        server_module.REPORTS_DIR = tmp_path / "reports"
        server_module.REPORTS_DIR.mkdir(exist_ok=True)
        server_module.ENDPOINTS_FILE = tmp_path / "endpoints.json"
        server_module.MODELS_FILE = tmp_path / "models.json"

        yield TestClient(app)

        server_module.GUI_DATA_DIR = orig_data_dir
        server_module.REPORTS_DIR = orig_reports_dir
        server_module.ENDPOINTS_FILE = orig_endpoints_file
        server_module.MODELS_FILE = orig_models_file

    def test_create_endpoint_encrypts_api_key_at_rest(self, client, tmp_path):
        """Test that API keys are encrypted before being stored in endpoints.json."""
        fake_key = "sk-test-api-key-12345678901234567890"
        response = client.post("/api/endpoints", json={
            "url": "https://api.example.com/v1",
            "apiKey": fake_key,
            "name": "Test Endpoint",
            "provider": "openai",
        })
        assert response.status_code == 200

        # Check the stored file - API key must NOT be in plaintext
        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        assert len(endpoints) == 1
        ep = endpoints[0]

        # Must not have plaintext apiKey
        assert "apiKey" not in ep
        # Must have encryptedApiKey
        assert "encryptedApiKey" in ep
        assert ep["encryptedApiKey"] != fake_key
        assert fake_key not in ep["encryptedApiKey"]
        assert ep["encryptedApiKey"].startswith("enc:")

    def test_create_endpoint_strips_api_key_from_response(self, client):
        """Test that API key is not returned in the POST /api/endpoints response."""
        fake_key = "sk-test-api-key-12345678901234567890"
        response = client.post("/api/endpoints", json={
            "url": "https://api.example.com/v1",
            "apiKey": fake_key,
            "name": "Test Endpoint",
            "provider": "openai",
        })
        assert response.status_code == 200
        data = response.json()
        assert "endpoint" in data
        ep = data["endpoint"]
        assert "apiKey" not in ep
        assert "encryptedApiKey" not in ep
        assert "keyFile" not in ep
        assert fake_key not in json.dumps(data)

    def test_list_endpoints_strips_api_key(self, client, tmp_path):
        """Test that GET /api/endpoints never returns API keys."""
        fake_key = "sk-test-api-key-12345678901234567890"
        # Create an endpoint first
        client.post("/api/endpoints", json={
            "url": "https://api.example.com/v1",
            "apiKey": fake_key,
            "name": "Test Endpoint",
            "provider": "openai",
        })

        # Now list endpoints
        response = client.get("/api/endpoints")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        assert len(data["endpoints"]) == 1
        ep = data["endpoints"][0]
        assert "apiKey" not in ep
        assert "encryptedApiKey" not in ep
        assert fake_key not in json.dumps(data)

    def test_list_endpoints_strips_legacy_plaintext_keys(self, client, tmp_path):
        """Test that even legacy plaintext apiKey fields are stripped from responses."""
        # Manually write an endpoint with legacy plaintext apiKey
        endpoints = [
            {
                "id": "ep_legacy",
                "name": "Legacy Endpoint",
                "url": "https://api.example.com/v1",
                "apiKey": "sk-legacy-plaintext-key-1234567890",
                "provider": "openai",
                "createdAt": "2026-01-01T00:00:00+00:00",
                "available": True,
                "lastTested": "2026-01-01T00:00:00+00:00",
            }
        ]
        (tmp_path / "endpoints.json").write_text(json.dumps(endpoints))

        response = client.get("/api/endpoints")
        assert response.status_code == 200
        data = response.json()
        ep = data["endpoints"][0]
        assert "apiKey" not in ep
        assert "sk-legacy-plaintext-key-1234567890" not in json.dumps(data)

    def test_kilo_login_encrypts_api_key_at_rest(self, client, tmp_path, monkeypatch):
        """Test that Kilo login encrypts the API key before persistence."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "model-1"}]}

        async def async_get(*args, **kwargs):
            return mock_resp

        mock_client.get = async_get

        async def async_enter(self):
            return self

        async def async_exit(self, *args):
            pass

        mock_client.__aenter__ = async_enter
        mock_client.__aexit__ = async_exit
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **kw: mock_client)

        fake_key = "sk-kilo-test-key-12345678901234567890"
        response = client.post("/api/kilo/login", json={
            "url": "https://api.kilo.ai/api/gateway",
            "apiKey": fake_key,
        })
        assert response.status_code == 200

        endpoints = json.loads((tmp_path / "endpoints.json").read_text())
        kilo_ep = next(e for e in endpoints if e.get("provider") == "kilo")
        assert "apiKey" not in kilo_ep
        assert "encryptedApiKey" in kilo_ep
        assert kilo_ep["encryptedApiKey"].startswith("enc:")
        assert fake_key not in json.dumps(endpoints)

    def test_sanitize_output_redacts_api_keys(self):
        """Test that sanitize_output redacts API key patterns."""
        from src.wilson_eval3ngine.gui.api_key_vault import sanitize_output

        text = "Making request with key sk-abcdefghijklmnopqrstuvwxyz123456"
        result = sanitize_output(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED_API_KEY]" in result

    def test_sanitize_output_redacts_bearer_tokens(self):
        """Test that sanitize_output redacts Bearer tokens."""
        from src.wilson_eval3ngine.gui.api_key_vault import sanitize_output

        text = "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456"
        result = sanitize_output(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        # The sk- pattern is matched first, so Bearer token is redacted via [REDACTED_API_KEY]
        assert "[REDACTED" in result

    def test_sanitize_output_redacts_json_api_key(self):
        """Test that sanitize_output redacts JSON apiKey fields."""
        from src.wilson_eval3ngine.gui.api_key_vault import sanitize_output

        text = '{"apiKey": "sk-secretvalue12345678901234567890"}'
        result = sanitize_output(text)
        assert "sk-secretvalue12345678901234567890" not in result
        assert "[REDACTED]" in result

    def test_sanitize_output_truncates_long_text(self):
        """Test that sanitize_output truncates very long text."""
        from src.wilson_eval3ngine.gui.api_key_vault import sanitize_output

        long_text = "A" * 10000
        result = sanitize_output(long_text)
        assert len(result) < 10000
        assert "[truncated]" in result

    def test_mask_api_key(self):
        """Test that mask_api_key properly masks keys."""
        from src.wilson_eval3ngine.gui.api_key_vault import mask_api_key

        key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = mask_api_key(key)
        assert "sk-a" in masked
        assert "****" in masked
        assert key not in masked
        assert masked.endswith("7890")

    def test_encrypt_decrypt_api_key_roundtrip(self):
        """Test that encrypt/decrypt roundtrip works correctly."""
        from src.wilson_eval3ngine.gui.api_key_vault import encrypt_api_key, decrypt_api_key

        key = "sk-roundtrip-test-key-12345678901234567890"
        encrypted = encrypt_api_key(key)
        assert encrypted.startswith("enc:")
        assert key not in encrypted

        decrypted = decrypt_api_key(encrypted)
        assert decrypted == key

    def test_decrypt_api_key_handles_empty(self):
        """Test that decrypt_api_key handles empty/None input."""
        from src.wilson_eval3ngine.gui.api_key_vault import decrypt_api_key

        assert decrypt_api_key("") == ""
        assert decrypt_api_key(None) == ""

    def test_encrypt_api_key_handles_empty(self):
        """Test that encrypt_api_key handles empty/None input."""
        from src.wilson_eval3ngine.gui.api_key_vault import encrypt_api_key

        assert encrypt_api_key("") == ""
        assert encrypt_api_key(None) == ""


class TestOAuthTokenSecurity:
    """Tests for OAuth token reading and file permission validation."""

    def test_read_kilo_oauth_token_returns_none_when_no_file(self, tmp_path):
        """Test that _read_kilo_oauth_token returns None when auth file doesn't exist."""
        from src.wilson_eval3ngine.gui.server import _read_kilo_oauth_token

        with patch("src.wilson_eval3ngine.gui.server.Path.home", return_value=tmp_path):
            result = _read_kilo_oauth_token()
            assert result is None

    def test_read_kilo_oauth_token_rejects_insecure_permissions(self, tmp_path):
        """Test that _read_kilo_oauth_token rejects files with group/other read access."""
        from src.wilson_eval3ngine.gui.server import _read_kilo_oauth_token

        auth_dir = tmp_path / ".local" / "share" / "kilo"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text(json.dumps({
            "kilo": {"access": "test-token-12345", "refresh": "refresh-token"}
        }))
        # Set insecure permissions (readable by group)
        auth_file.chmod(0o640)

        with patch("src.wilson_eval3ngine.gui.server.Path.home", return_value=tmp_path):
            result = _read_kilo_oauth_token()
            assert result is None

    def test_read_kilo_oauth_token_accepts_secure_permissions(self, tmp_path):
        """Test that _read_kilo_oauth_token reads token when file has 0600 permissions."""
        from src.wilson_eval3ngine.gui.server import _read_kilo_oauth_token

        auth_dir = tmp_path / ".local" / "share" / "kilo"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text(json.dumps({
            "kilo": {"access": "test-token-12345", "refresh": "refresh-token"}
        }))
        # Set secure permissions (owner-only)
        auth_file.chmod(0o600)

        with patch("src.wilson_eval3ngine.gui.server.Path.home", return_value=tmp_path):
            result = _read_kilo_oauth_token()
            assert result == "test-token-12345"

    def test_read_kilo_oauth_token_handles_corrupt_json(self, tmp_path):
        """Test that _read_kilo_oauth_token returns None for corrupt JSON."""
        from src.wilson_eval3ngine.gui.server import _read_kilo_oauth_token

        auth_dir = tmp_path / ".local" / "share" / "kilo"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text("not valid json{{{")
        auth_file.chmod(0o600)

        with patch("src.wilson_eval3ngine.gui.server.Path.home", return_value=tmp_path):
            result = _read_kilo_oauth_token()
            assert result is None

    def test_read_kilo_oauth_token_handles_missing_access_key(self, tmp_path):
        """Test that _read_kilo_oauth_token returns None when access key is missing."""
        from src.wilson_eval3ngine.gui.server import _read_kilo_oauth_token

        auth_dir = tmp_path / ".local" / "share" / "kilo"
        auth_dir.mkdir(parents=True)
        auth_file = auth_dir / "auth.json"
        auth_file.write_text(json.dumps({"kilo": {"refresh": "refresh-token"}}))
        auth_file.chmod(0o600)

        with patch("src.wilson_eval3ngine.gui.server.Path.home", return_value=tmp_path):
            result = _read_kilo_oauth_token()
            assert result is None


class TestSSRFProtection:
    """Tests for SSRF protection in gateway URL validation."""

    def test_validate_gateway_url_accepts_https(self):
        """Test that HTTPS URLs are accepted."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("https://api.kilo.ai/api/gateway")
        assert valid is True
        assert err == ""

    def test_validate_gateway_url_rejects_localhost(self):
        """Test that localhost URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("http://localhost:11434")
        assert valid is False
        assert "localhost" in err.lower()

    def test_validate_gateway_url_rejects_127(self):
        """Test that 127.x.x.x URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("http://127.0.0.1:8000")
        assert valid is False

    def test_validate_gateway_url_rejects_private_ip_10(self):
        """Test that 10.x.x.x URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("http://10.133.7.211:11434")
        assert valid is False

    def test_validate_gateway_url_rejects_private_ip_172(self):
        """Test that 172.16-31.x.x URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("http://172.16.0.1:8000")
        assert valid is False

    def test_validate_gateway_url_rejects_private_ip_192(self):
        """Test that 192.168.x.x URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("http://192.168.1.1:8000")
        assert valid is False

    def test_validate_gateway_url_rejects_non_http(self):
        """Test that non-HTTP schemes are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("ftp://evil.com/file")
        assert valid is False

    def test_validate_gateway_url_rejects_empty(self):
        """Test that empty URLs are rejected."""
        from scripts.generate_5_reports import _validate_gateway_url

        valid, err = _validate_gateway_url("")
        assert valid is False


class TestAPIKeyMasking:
    """Tests for API key masking in logs."""

    def test_mask_api_key_masks_long_key(self):
        """Test that long API keys are properly masked."""
        from scripts.generate_5_reports import _mask_api_key

        key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        masked = _mask_api_key(key)
        assert "sk-a" in masked
        assert "..." in masked
        assert "7890" in masked
        assert key not in masked

    def test_mask_api_key_redacts_short_key(self):
        """Test that short keys are fully redacted."""
        from scripts.generate_5_reports import _mask_api_key

        assert _mask_api_key("short") == "***REDACTED***"
        assert _mask_api_key("") == "***REDACTED***"


class TestResponseHandler:
    """Tests for the reasoning-aware response handler."""

    def test_parse_reasoning_response(self):
        """Test parsing of reasoning model response (content=null, reasoning present)."""
        from wilson_eval3ngine.responses import parse_response

        data = {
            "choices": [{
                "message": {
                    "content": None,
                    "reasoning": "Let me think about this step by step...",
                    "reasoning_details": [
                        {"type": "reasoning.text", "text": "Let me think about this step by step..."}
                    ]
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 20}
            },
            "model": "stepfun/step-3.7-flash",
            "provider": "StepFun"
        }
        parsed = parse_response(data)
        assert parsed.is_reasoning is True
        assert parsed.text == "Let me think about this step by step..."
        assert parsed.reasoning == "Let me think about this step by step..."
        assert parsed.reasoning_tokens == 20
        assert parsed.completion_tokens == 20

    def test_parse_content_response(self):
        """Test parsing of standard content model response."""
        from wilson_eval3ngine.responses import parse_response

        data = {
            "choices": [{
                "message": {
                    "content": "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)",
                    "reasoning": None
                }
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            "model": "gpt-4o",
            "provider": "OpenAI"
        }
        parsed = parse_response(data)
        assert parsed.is_reasoning is False
        assert parsed.content == "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
        assert parsed.has_code is True

    def test_parse_hybrid_response(self):
        """Test parsing of hybrid response (both content and reasoning present)."""
        from wilson_eval3ngine.responses import parse_response

        data = {
            "choices": [{
                "message": {
                    "content": "Here is the answer",
                    "reasoning": "Let me think...",
                    "reasoning_details": [{"type": "reasoning.text", "text": "Let me think..."}]
                }
            }],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 10,
                "total_tokens": 15,
                "completion_tokens_details": {"reasoning_tokens": 5}
            },
            "model": "nvidia/nemotron-3-super-120b",
            "provider": "NVIDIA"
        }
        parsed = parse_response(data)
        assert parsed.has_both is True
        assert parsed.content == "Here is the answer"
        assert parsed.reasoning == "Let me think..."
        assert parsed.text == "Here is the answer"
        assert parsed.reasoning_tokens == 5

    def test_parse_ollama_response(self):
        """Test parsing of Ollama-style response."""
        from wilson_eval3ngine.responses import parse_response

        data = {
            "message": {
                "content": "Quantum computing uses qubits...",
            },
            "eval_count": 15,
            "model": "llama3.2",
            "provider": "Ollama"
        }
        parsed = parse_response(data)
        assert parsed.is_reasoning is False
        assert parsed.content == "Quantum computing uses qubits..."
        assert parsed.text == "Quantum computing uses qubits..."

    def test_model_response_has_code_detection(self):
        """Test that has_code property detects code in response."""
        from wilson_eval3ngine.responses import ModelResponse

        resp = ModelResponse(text="def hello(): return 'world'")
        assert resp.has_code is True

        resp2 = ModelResponse(text="This is just a regular response")
        assert resp2.has_code is False

    def test_model_response_has_security_detection(self):
        """Test that has_security property detects security terms."""
        from wilson_eval3ngine.responses import ModelResponse

        resp = ModelResponse(text="Security vulnerability: SQL injection risk")
        assert resp.has_security is True

        resp2 = ModelResponse(text="This is just a regular response")
        assert resp2.has_security is False
