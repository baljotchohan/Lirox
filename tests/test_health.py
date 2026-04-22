from lirox.core.health import run_health_checks


def test_health_report_shape():
    report = run_health_checks(strict=False)
    payload = report.as_dict()
    assert "ok" in payload
    assert "checks" in payload
    names = {c["name"] for c in payload["checks"]}
    assert {"config", "workspace", "database", "execution", "documents", "llm"}.issubset(names)

