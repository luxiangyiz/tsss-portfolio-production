from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_start_script_binds_localhost_and_enables_offline_mode():
    text = (ROOT / "scripts" / "start_local_demo.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts" / "local_demo_launcher.py").read_text(encoding="utf-8")
    assert "local_demo_launcher.py" in text
    assert '"DEMO_HOST": "127.0.0.1"' in launcher
    assert '"API_HOST": "127.0.0.1"' in launcher
    assert '"RAG_RUNTIME_MODE": "offline_demo"' in launcher
    assert "CREATE_NO_WINDOW" in launcher


def test_stop_script_targets_only_recorded_pid():
    text = (ROOT / "scripts" / "stop_local_demo.ps1").read_text(encoding="utf-8")
    assert "Stop-Process -Id $demoProcessId" in text
    assert "Get-Process python" not in text
    assert "rag_app\\.main" in text


def test_verify_script_checks_required_endpoints():
    text = (ROOT / "scripts" / "verify_local_demo.ps1").read_text(encoding="utf-8")
    for endpoint in ("/health", "/demo", "/ingest/preview", "/index/stats"):
        assert endpoint in text
