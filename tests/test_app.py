import pytest

from app import main


@pytest.fixture
def client(monkeypatch):
    # Skip the simulated downstream delay so tests stay fast
    monkeypatch.setattr(main.time, "sleep", lambda _: None)
    main.app.config["TESTING"] = True
    return main.app.test_client()


def test_home_shows_service_and_version(client):
    res = client.get("/")
    assert res.status_code == 200
    assert res.get_json() == {"service": "catalog-service", "version": main.APP_VERSION}


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_list_titles(client):
    res = client.get("/titles")
    assert res.status_code == 200
    assert len(res.get_json()) == len(main.TITLES)


def test_get_single_title(client):
    res = client.get("/titles/3")
    assert res.status_code == 200
    assert res.get_json()["title"] == "Pipeline Dreams"


def test_missing_title_returns_404(client):
    assert client.get("/titles/999").status_code == 404


def test_recommendations_success(client, monkeypatch):
    monkeypatch.setattr(main, "FAILURE_RATE", 0.0)
    res = client.get("/recommendations")
    assert res.status_code == 200
    assert len(res.get_json()) == 3


def test_recommendations_failure(client, monkeypatch):
    monkeypatch.setattr(main, "FAILURE_RATE", 1.0)
    res = client.get("/recommendations")
    assert res.status_code == 503


def test_metrics_are_exposed(client):
    client.get("/titles")
    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
