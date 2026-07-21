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
        
        # Pre-create the endpoint
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
