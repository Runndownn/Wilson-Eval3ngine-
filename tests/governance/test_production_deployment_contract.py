from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.prod.yml"
SECURE_COMPOSE = ROOT / "docker-compose.secure.yml"
DOCKERFILE = ROOT / "Dockerfile.prod"
SECURE_DOCKERFILE = ROOT / "Dockerfile.secure"
CADDYFILE = ROOT / "infrastructure" / "caddy" / "Caddyfile"


def _compose(path: Path = COMPOSE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_only_tls_proxy_publishes_host_ports() -> None:
    services = _compose()["services"]
    assert set(services["caddy"]["ports"]) == {"80:80", "443:443"}
    for name in {
        "api",
        "postgres",
        "redis",
        "prometheus",
        "grafana",
        "egress-proxy",
    }:
        assert "ports" not in services[name], f"{name} must not bypass the TLS proxy"


def test_all_runtime_images_require_operator_supplied_immutable_references() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    for variable in {
        "WE3_API_IMAGE",
        "WE3_POSTGRES_IMAGE",
        "WE3_REDIS_IMAGE",
        "WE3_CADDY_IMAGE",
        "WE3_PROMETHEUS_IMAGE",
        "WE3_GRAFANA_IMAGE",
        "WE3_EGRESS_PROXY_IMAGE",
    }:
        assert f"${{{variable}:?digest-pinned" in compose
    assert "image: postgres:" not in compose
    assert "image: redis:" not in compose
    assert "image: caddy:" not in compose


def test_api_uses_mounted_secret_authority_not_secret_environment_values() -> None:
    service = _compose()["services"]["api"]
    environment = service["environment"]
    assert environment["WE3_SECRET_BACKEND"] == "mounted"
    assert environment["WE3_SECRET_MOUNT"] == "/run/secrets"

    for secret_name in {
        "WE3_DATABASE_URL",
        "WE3_REDIS_URL",
        "WE3_ENCRYPTION_KEY",
        "WE3_CSRF_SECRET",
    }:
        assert secret_name not in environment

    targets = {entry["target"] for entry in service["secrets"]}
    assert {
        "DATABASE_URL",
        "REDIS_URL",
        "ENCRYPTION_KEY",
        "CSRF_SECRET",
    }.issubset(targets)


def test_database_and_cache_credentials_are_file_backed() -> None:
    compose = _compose()
    assert compose["services"]["postgres"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/POSTGRES_PASSWORD"
    assert compose["services"]["redis"]["environment"]["REDIS_PASSWORD_FILE"] == "/run/secrets/REDIS_PASSWORD"
    assert "WE3_POSTGRES_PASSWORD" not in compose["services"]["postgres"]["environment"]
    assert "WE3_REDIS_PASSWORD" not in compose["services"]["redis"]["environment"]


def test_postgresql_transport_and_cache_protection_are_explicit() -> None:
    compose = _compose()
    postgres_command = compose["services"]["postgres"]["command"]
    assert "ssl=on" in postgres_command
    assert "password_encryption=scram-sha-256" in postgres_command
    redis_command = " ".join(compose["services"]["redis"]["command"])
    assert "--requirepass" in redis_command
    assert "--protected-mode yes" in redis_command


def test_api_egress_is_routed_through_explicit_proxy_boundary() -> None:
    service = _compose()["services"]["api"]
    environment = service["environment"]
    assert environment["HTTP_PROXY"] == "http://egress-proxy:3128"
    assert environment["HTTPS_PROXY"] == "http://egress-proxy:3128"
    assert "egress_internal" in service["networks"]
    proxy = _compose()["services"]["egress-proxy"]
    assert "egress_uplink" in proxy["networks"]
    assert "ports" not in proxy


def test_monitoring_admin_api_is_not_enabled() -> None:
    command = _compose()["services"]["prometheus"]["command"]
    assert "--web.enable-admin-api" not in command
    assert "--web.enable-lifecycle" not in command


def test_non_public_networks_are_internal() -> None:
    networks = _compose()["networks"]
    for name in {"ingress", "data", "observability", "egress_internal"}:
        assert networks[name]["internal"] is True
    assert networks["public"].get("internal", False) is False
    assert networks["egress_uplink"].get("internal", False) is False


def test_production_image_requires_immutable_base_and_secure_entrypoint() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ARG PYTHON_BASE_IMAGE" in text
    assert "FROM ${PYTHON_BASE_IMAGE} AS builder" in text
    assert "FROM ${PYTHON_BASE_IMAGE} AS runtime" in text
    assert "COPY src ./src" in text
    assert "python -m build --wheel --no-isolation" in text
    assert "--no-index --find-links=/tmp/wheels" in text
    assert '"redis>=5,<6"' in text
    assert "wilson_eval3ngine.api.secure_entrypoint:app" in text
    assert "USER 10001:10001" in text


def test_prod_and_secure_profiles_share_security_critical_contracts() -> None:
    prod = _compose(COMPOSE)
    secure = _compose(SECURE_COMPOSE)
    for service in {
        "postgres",
        "redis",
        "api",
        "egress-proxy",
        "caddy",
        "prometheus",
        "grafana",
    }:
        assert prod["services"][service]["image"] == secure["services"][service]["image"]
        assert prod["services"][service].get("ports") == secure["services"][service].get("ports")
        assert prod["services"][service].get("cap_drop") == secure["services"][service].get("cap_drop")

    prod_docker = DOCKERFILE.read_text(encoding="utf-8")
    secure_docker = SECURE_DOCKERFILE.read_text(encoding="utf-8")
    for required in {
        "ARG PYTHON_BASE_IMAGE",
        "wilson_eval3ngine.api.secure_entrypoint:app",
        '"redis>=5,<6"',
        "USER 10001:10001",
    }:
        assert required in prod_docker
        assert required in secure_docker


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
