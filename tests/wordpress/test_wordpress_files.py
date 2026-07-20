import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORDPRESS = ROOT / "src" / "wordpress"
THEME = WORDPRESS / "themes" / "zwd-portfolio"
PLUGIN = WORDPRESS / "plugins" / "zwd-portfolio-core" / "zwd-portfolio-core.php"


def test_required_wordpress_files_exist():
    required = [
        WORDPRESS / ".wp-env.json",
        WORDPRESS / "package.json",
        THEME / "style.css",
        THEME / "theme.json",
        THEME / "functions.php",
        THEME / "parts" / "header.html",
        THEME / "parts" / "footer.html",
        THEME / "templates" / "front-page.html",
        THEME / "templates" / "archive-project.html",
        THEME / "templates" / "single-project.html",
        PLUGIN,
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing WordPress files: {missing}"


def test_json_files_are_valid_and_version_is_pinned():
    environment = json.loads((WORDPRESS / ".wp-env.json").read_text(encoding="utf-8"))
    theme = json.loads((THEME / "theme.json").read_text(encoding="utf-8"))
    package = json.loads((WORDPRESS / "package.json").read_text(encoding="utf-8"))

    assert environment["core"].endswith("wordpress-7.0.1.zip")
    assert environment["config"]["WP_ENVIRONMENT_TYPE"] == "local"
    assert theme["version"] == 3
    assert package["devDependencies"]["@wordpress/env"] == "11.11.0"


def test_project_templates_use_card_archive_and_longform_single():
    archive = (THEME / "templates" / "archive-project.html").read_text(encoding="utf-8")
    single = (THEME / "templates" / "single-project.html").read_text(encoding="utf-8")
    styles = (THEME / "style.css").read_text(encoding="utf-8")

    assert "project-card-grid" in archive
    assert "project-card" in archive
    assert "project-single" in single
    assert "grid-template-columns: repeat(2" in styles
    assert "@media (max-width: 720px)" in styles
    assert "grid-template-columns: 1fr" in styles


def test_plugin_enforces_public_source_gate_and_noindex():
    plugin = PLUGIN.read_text(encoding="utf-8")

    for marker in (
        "privacy_level",
        "publish_status",
        "review_status",
        "verification_status",
        "blog_public",
        "local_robots",
    ):
        assert marker in plugin

    assert "private" not in re.findall(r"'privacy_level'\s*=>\s*'([^']+)'", plugin)


def test_theme_does_not_load_remote_fonts_or_images():
    theme_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in THEME.rglob("*")
        if path.is_file() and path.suffix in {".css", ".php", ".html", ".json", ".md"}
    )
    assert "fonts.googleapis.com" not in theme_text
    assert "<img" not in theme_text
    assert "picsum.photos" not in theme_text
    assert "images.unsplash.com" not in theme_text


def test_homepage_v2_is_server_rendered_and_privacy_scoped():
    plugin_text = PLUGIN.read_text(encoding="utf-8")
    homepage_js = (THEME / "assets" / "src" / "components" / "RagAssistant.js").read_text(encoding="utf-8")
    navigation_js = (THEME / "assets" / "src" / "data" / "navigation-items.js").read_text(encoding="utf-8")

    assert "欢迎来到我的网站" in plugin_text
    assert 'action="/api/rag/public/ask"' in plugin_text
    assert "JSON.stringify({ question: value })" in homepage_js
    assert "window.zwdHomepageConfig" in homepage_js
    assert "AbortController" in homepage_js
    assert "index_scope" not in homepage_js
    assert "top_k" not in homepage_js
    assert navigation_js.count("href:") == 4
    assert "/insights/" not in navigation_js


def test_public_seed_contains_no_obvious_secret_or_phone():
    plugin = PLUGIN.read_text(encoding="utf-8")
    assert not re.search(r"\b1[3-9]\d{9}\b", plugin)
    assert not re.search(r"\bsk-[A-Za-z0-9_-]{12,}\b", plugin)
