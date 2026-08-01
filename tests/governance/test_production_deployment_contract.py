from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.prod.yml"
DOCKERFILE = ROOT / "Dockerfile.prod"
CADDYFILE = ROOT / "infrastructure" / "caddy" / "Caddyfile"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_only_tls_proxy_publishes_host_ports() -> None:
    services = _compose()["services"]

    assert set(services["caddy"]["ports"]) == {"80:80", "443:443"}
    for name in {"api", "postgres", "redis", "prometheus", "grafana"}:
        assert "ports" not in services[name], f"{name} must not bypass the TLS proxy"


def test_production_credentials_have_no_fallback_values() -> None:
    text = COMPOSE.read_text(encoding="utf-8")

    assert "we3-dev-password" not in text
    assert "WE3_GRAFANA_PASSWORD:-admin" not in text
    for variable in {
        "WE3_POSTGRES_PASSWORD",
        "WE3_REDIS_PASSWORD",
        "WE3_GRAFANA_PASSWORD",
        "WE3_OIDC_ISSUER",
        "WE3_OIDC_JWKS_URI",
        "WE3_DOMAIN",
        "WE3_TLS_EMAIL",
    }:
        assert f"${{{variable}:?" in text


def test_monitoring_admin_api_is_not_enabled() -> None:
    command = _compose()["services"]["prometheus"]["command"]

    assert "--web.enable-admin-api" not in command
    assert "--web.enable-lifecycle" not in command


def test_data_and_observability_networks_are_internal() -> None:
    networks = _compose()["networks"]

    assert networks["data"]["internal"] is True
    assert networks["observability"]["internal"] is True


def test_production_image_builds_wheel_before_runtime_install() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY src ./src" in text
    assert "python -m build --wheel --no-isolation" in text
    assert "--no-index --find-links=/tmp/wheels" in text
    assert "python -m gunicorn" not in text
    assert "python\", \"-m\", \"uvicorn" in text
    assert "USER 10001:10001" in text


def test_stock_caddy_contract_has_no_optional_plugin_directives() -> None:
    text = CADDYFILE.read_text(encoding="utf-8")

    assert "rate_limit" not in text
    assert "admin off" in text
    assert "protocols tls1.2 tls1.3" in text
    assert "reverse_proxy api:8000" in text
    assert "reverse_proxy prometheus:9090" in text
    assert "reverse_proxy grafana:3000" in text


def test_proxy_headers_are_site_scoped_and_metrics_are_restricted() -> None:
    text = CADDYFILE.read_text(encoding="utf-8")

    assert "(security_headers)" in text
    assert 'Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"' in text
    assert "@private_clients remote_ip" in text
    assert 'respond "Forbidden" 403' in text
