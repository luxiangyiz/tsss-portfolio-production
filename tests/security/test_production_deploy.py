"""Static and unit gates for the 2 vCPU / 2 GiB production deployment."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
RAG_API = ROOT / "rag-api"
DEPLOY = ROOT / "deploy"

if str(RAG_API) not in sys.path:
    sys.path.insert(0, str(RAG_API))


def load_compose() -> dict:
    return yaml.safe_load(
        (DEPLOY / "docker-compose.production.yml").read_text(encoding="utf-8")
    )


def test_compose_uses_four_runtime_services_and_embedded_qdrant():
    compose = load_compose()
    services = compose["services"]

    assert "qdrant" not in services
    assert {"nginx", "wordpress", "mysql", "rag-api"}.issubset(services)
    assert services["rag-index"]["profiles"] == ["tools"]
    assert services["wp-cli"]["profiles"] == ["admin"]
    assert services["certbot"]["profiles"] == ["tls"]

    rag = services["rag-api"]
    assert rag["environment"]["QDRANT_PATH"] == "/app/data/rag/qdrant"
    assert rag["environment"]["RAG_CONFIG_PATH"] == "/app/configs/rag_config.yaml"
    assert "QDRANT_URL" not in rag["environment"]
    assert "../public-content:/app/public-content:ro" in rag["volumes"]
    assert "rag_data:/app/data/rag" in rag["volumes"]
    assert rag["mem_limit"] == "512m"


def test_only_nginx_publishes_host_ports():
    services = load_compose()["services"]
    assert services["nginx"]["ports"] == ["80:80", "443:443"]
    for service_name in ("wordpress", "mysql", "rag-api", "rag-index", "wp-cli"):
        assert "ports" not in services[service_name]


def test_2g_memory_limits_and_single_worker():
    services = load_compose()["services"]
    assert services["nginx"]["mem_limit"] == "64m"
    assert services["wordpress"]["mem_limit"] == "320m"
    assert services["mysql"]["mem_limit"] == "384m"
    assert services["rag-api"]["mem_limit"] == "512m"

    dockerfile = (RAG_API / "Dockerfile").read_text(encoding="utf-8")
    assert '"--workers", "1"' in dockerfile
    assert '"--workers", "2"' not in dockerfile


def test_nginx_uses_fastcgi_prefix_stripping_and_tls_bootstrap():
    http_config = (DEPLOY / "nginx" / "site-http.conf.template").read_text(
        encoding="utf-8"
    )
    https_config = (DEPLOY / "nginx" / "site-https.conf.template").read_text(
        encoding="utf-8"
    )
    overlay = (DEPLOY / "docker-compose.https.yml").read_text(encoding="utf-8")

    assert "server wordpress:9000;" in http_config
    assert "fastcgi_pass wordpress_backend;" in http_config
    assert "proxy_pass http://rag_api_backend/;" in http_config
    assert "ssl_certificate" not in http_config
    assert "site-https.conf.template" in overlay
    assert "ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;" in https_config
    assert "return 301 https://${DOMAIN}$request_uri;" in https_config


def test_wordpress_public_sources_and_admin_profile_are_present():
    services = load_compose()["services"]
    wordpress = services["wordpress"]
    wp_cli = services["wp-cli"]

    source_mount = (
        "../public-content:/var/www/html/wp-content/zwd-public-sources:ro"
    )
    assert source_mount in wordpress["volumes"]
    assert source_mount in wp_cli["volumes"]
    assert wp_cli["user"] == "82:82"
    assert "ZWD_RAG_PUBLIC_URL" in wordpress["environment"]["WORDPRESS_CONFIG_EXTRA"]


def test_production_scripts_have_required_safety_markers():
    scripts = {
        path.name: path.read_text(encoding="utf-8")
        for path in (DEPLOY / "scripts").glob("*.sh")
    }

    assert "checkout --detach" in scripts["deploy.sh"]
    assert "require_clean_repository" in scripts["deploy.sh"]
    assert "failed-health" in scripts["deploy.sh"]
    assert "source-sync-manifest.json" in scripts["backup.sh"]
    assert "public-source-manifest.json" not in scripts["backup.sh"]
    assert "zwd_rag_data" in scripts["backup.sh"]
    assert "Type YES to continue" in scripts["restore.sh"]
    assert "--scope public" in scripts["index-public.sh"]
    assert "wp zwd verify" in scripts["init-wordpress.sh"]


@pytest.mark.skipif(os.name == "nt", reason="Bash path semantics are validated in Linux CI")
def test_shell_scripts_parse():
    scripts = sorted((DEPLOY / "scripts").glob("*.sh"))
    result = subprocess.run(
        ["bash", "-n", *map(str, scripts)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def production_settings(monkeypatch):
    from rag_app.core.config import settings

    values = {
        "rag_runtime_mode": "real_remote",
        "app_env": "production",
        "allow_fake_mode": False,
        "api_host": "0.0.0.0",
        "embedding_api_key": "unit-test-embedding-value",
        "llm_api_key": "unit-test-llm-value",
        "qdrant_url": None,
        "cors_origins": "https://portfolio.invalid",
        "default_index_scope": "public",
        "rag_max_concurrent": 2,
        "public_expected_documents": 9,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    return settings


def test_real_remote_security_accepts_hardened_production(production_settings):
    from rag_app.core.config import validate_runtime_security

    validate_runtime_security()


def test_public_yaml_configuration_is_loaded():
    from rag_app.core.config import settings

    assert settings.yaml_config["collections"] == {"public": "kb_public"}
    assert settings.yaml_config["knowledge_base"]["root"] == "/app/public-content"
    assert "verified" in settings.yaml_config["metadata"]["verification_status"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_env", "development"),
        ("allow_fake_mode", True),
        ("api_host", "127.0.0.1"),
        ("embedding_api_key", None),
        ("llm_api_key", None),
        ("qdrant_url", "http://qdrant:6333"),
        ("cors_origins", "*"),
        ("default_index_scope", "internal"),
        ("rag_max_concurrent", 3),
    ],
)
def test_real_remote_security_rejects_unsafe_combinations(
    production_settings, monkeypatch, field, value
):
    from rag_app.core.config import settings, validate_runtime_security

    monkeypatch.setattr(settings, field, value)
    with pytest.raises(ValueError):
        validate_runtime_security()


def test_public_index_cli_only_accepts_public_scope():
    from rag_app.cli import build_parser

    parser = build_parser()
    accepted = parser.parse_args(["index", "--scope", "public", "--mode", "full"])
    assert accepted.scope == "public"

    with pytest.raises(SystemExit):
        parser.parse_args(["index", "--scope", "internal", "--mode", "full"])


def test_public_index_cli_builds_only_public_collection(tmp_path, monkeypatch):
    from rag_app.cli import run_public_index
    from rag_app.core.config import settings
    from rag_app.langchain_components import vector_store

    values = {
        "kb_root": str(ROOT / "public-content"),
        "rag_data_dir": str(tmp_path),
        "qdrant_path": str(tmp_path / "qdrant"),
        "qdrant_url": None,
        "rag_runtime_mode": "offline_demo",
        "allow_fake_mode": True,
        "demo_host": "127.0.0.1",
        "api_host": "127.0.0.1",
        "cors_origins": "",
        "default_index_scope": "public",
        "embedding_dimension": 1536,
        "public_expected_documents": 9,
        "rag_max_concurrent": 2,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)

    vector_store._client = None
    try:
        result = run_public_index("full")
        assert result["scanned_files"] == 9
        assert result["included_files"] == 9
        assert result["indexed_documents"] == 9
        assert result["collections"] == ["kb_public"]
        assert result["written_chunks"] > 0
        incremental = run_public_index("incremental")
        assert incremental["written_chunks"] == 0
        assert incremental["indexed_documents"] == 9
        assert incremental["collections"] == ["kb_public"]
    finally:
        if vector_store._client is not None:
            vector_store._client.close()
        vector_store._client = None


def test_public_app_exposes_only_public_health_and_routes(monkeypatch):
    from fastapi.testclient import TestClient
    from rag_app.api import public
    from rag_app.public_main import app

    monkeypatch.setattr(
        public,
        "get_collection_info",
        lambda _name: {"name": "kb_public", "points_count": 12},
    )
    with TestClient(app) as client:
        assert client.get("/public/health/live").status_code == 200
        ready = client.get("/public/health/ready")
        assert ready.status_code == 200
        assert ready.json()["points_count"] == 12
        assert client.post("/ingest", json={}).status_code == 404
        assert client.post("/ask", json={"question": "x"}).status_code == 404
        assert client.get("/docs").status_code == 404


def test_public_ready_reports_unavailable_index_as_503(monkeypatch):
    from fastapi.testclient import TestClient
    from rag_app.api import public
    from rag_app.public_main import app

    monkeypatch.setattr(
        public,
        "get_collection_info",
        lambda _name: {
            "name": "kb_public",
            "points_count": 0,
            "error": "not found",
        },
    )
    with TestClient(app) as client:
        response = client.get("/public/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "reason": "public_index_unavailable",
        }
