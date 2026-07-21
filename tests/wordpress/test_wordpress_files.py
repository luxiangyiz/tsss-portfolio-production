import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORDPRESS = ROOT / "src" / "wordpress"
if not WORDPRESS.exists():
    WORDPRESS = ROOT / "wordpress"
IS_SOURCE_REPOSITORY = (WORDPRESS / ".wp-env.json").exists()
THEME = WORDPRESS / "themes" / "zwd-portfolio"
PLUGIN = WORDPRESS / "plugins" / "zwd-portfolio-core" / "zwd-portfolio-core.php"


def test_required_single_page_files_exist():
    required = [
        THEME / "style.css",
        THEME / "theme.json",
        THEME / "functions.php",
        THEME / "parts" / "header.html",
        THEME / "parts" / "footer.html",
        THEME / "templates" / "front-page.html",
        THEME / "templates" / "single-project.html",
        THEME / "assets" / "images" / "hero-portrait.png",
        THEME / "assets" / "src" / "components" / "ProjectCarousel.js",
        PLUGIN,
    ]
    if IS_SOURCE_REPOSITORY:
        required.extend([WORDPRESS / ".wp-env.json", WORDPRESS / "package.json"])
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing WordPress files: {missing}"
    assert not (THEME / "templates" / "archive-project.html").exists()


def test_json_files_are_valid_and_dependencies_are_minimal():
    if not IS_SOURCE_REPOSITORY:
        assert (ROOT / "deploy" / "docker-compose.production.yml").exists()
        return

    environment = json.loads((WORDPRESS / ".wp-env.json").read_text(encoding="utf-8"))
    theme = json.loads((THEME / "theme.json").read_text(encoding="utf-8"))
    package = json.loads((WORDPRESS / "package.json").read_text(encoding="utf-8"))

    assert environment["phpVersion"] == "8.3"
    assert environment["config"]["WP_ENVIRONMENT_TYPE"] == "local"
    assert theme["version"] == 3
    assert package["devDependencies"]["@wordpress/env"] == "11.11.0"
    assert "ogl" not in package.get("dependencies", {})


def test_projects_are_dynamic_cards_with_public_detail_pages():
    plugin = PLUGIN.read_text(encoding="utf-8")
    carousel = (THEME / "assets" / "src" / "components" / "ProjectCarousel.js").read_text(encoding="utf-8")
    styles = (THEME / "assets" / "src" / "homepage.css").read_text(encoding="utf-8")

    assert "zwd_project_gallery" in plugin
    assert "get_posts" in plugin
    assert "posts_per_page' => -1" in plugin
    assert re.search(r"'publicly_queryable'\s*=>\s*true", plugin)
    assert "'slug'       => 'projects'" in plugin
    assert "migrate-single-page" in plugin
    assert "template_redirect" in plugin
    assert "data-project-card" in carousel
    assert "dragstart" in carousel
    assert "draggable = false" in carousel
    assert "scroll-snap-type: x mandatory" in styles
    assert "overflow-x: auto" in styles


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


def test_theme_uses_only_local_visual_assets():
    theme_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in THEME.rglob("*")
        if path.is_file() and path.suffix in {".css", ".php", ".html", ".json", ".md"}
    )
    assert "fonts.googleapis.com" not in theme_text
    assert "picsum.photos" not in theme_text
    assert "images.unsplash.com" not in theme_text
    assert (THEME / "assets" / "images" / "hero-portrait.png").stat().st_size > 0


def test_homepage_is_single_page_and_rag_is_public_scoped():
    plugin_text = PLUGIN.read_text(encoding="utf-8")
    homepage_js = (THEME / "assets" / "src" / "components" / "RagAssistant.js").read_text(encoding="utf-8")
    header = (THEME / "parts" / "header.html").read_text(encoding="utf-8")

    for section_id in ("top", "projects", "about", "resume", "contact"):
        assert f'id="{section_id}"' in plugin_text
    assert "[zwd_project_gallery]" in plugin_text
    assert 'action="/public/ask"' in plugin_text
    assert "JSON.stringify({ question: value })" in homepage_js
    assert "window.zwdHomepageConfig" in homepage_js
    assert "AbortController" in homepage_js
    assert "index_scope" not in homepage_js
    assert "top_k" not in homepage_js
    assert "/#projects" in header
    assert "/insights/" not in header


def test_public_seed_contains_no_obvious_secret():
    plugin = PLUGIN.read_text(encoding="utf-8")
    assert not re.search(r"\bsk-[A-Za-z0-9_-]{12,}\b", plugin)
