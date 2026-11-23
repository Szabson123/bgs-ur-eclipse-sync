from fastapi.testclient import TestClient

import main
from sync import SyncService
from tests.test_sync import FakeBgs, ch


def test_health_and_manual_run(monkeypatch):
    fake = FakeBgs([ch("A")], outcome="baseline")
    monkeypatch.setattr(main, "service", SyncService(fake, lambda codes: {"A": 10}))
    with TestClient(main.app) as client:
        health = client.get("/health").json()
        assert health["status"] == "starting"
        assert health["scheduler_enabled"] is False

        run = client.post("/sync/run").json()
        assert run["last_results"] == {"A": "baseline"}

        health = client.get("/health").json()
        assert (health["status"], health["runs"], health["channels"]) == ("ok", 1, 1)


def test_health_reports_error(monkeypatch):
    def broken(codes):
        raise RuntimeError("Login failed")
    monkeypatch.setattr(main, "service", SyncService(FakeBgs([ch("A")]), broken))
    with TestClient(main.app) as client:
        client.post("/sync/run")
        health = client.get("/health").json()
    assert health["status"] == "error"
    assert "Login failed" in health["last_error"]
