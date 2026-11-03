import importlib
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from motif.llm import FixtureClient
from motif.pipeline import process_book
from motif.store import Store


def test_api_serves_demo_with_provenance(tmp_path, monkeypatch, settings, cave):
    db = tmp_path / "demo.db"
    process_book(cave, FixtureClient(settings.demo_dir / "plato_cave.fixture.json"), Store(db), log=lambda _: None)
    monkeypatch.setenv("MOTIF_DEMO", "1")
    monkeypatch.setenv("MOTIF_DEMO_DB", str(db))
    import motif.api
    api = importlib.reload(motif.api)
    client = TestClient(api.app)

    assert client.get("/api/health").json()["mode"] == "demo"
    books = client.get("/api/books").json()
    assert books[0]["provenance"] == "demo-fixture"
    snap = client.get("/api/books/plato_cave").json()
    assert len(snap["passages"]) == 9 and snap["units"] and snap["relations"]
    top = client.get("/api/books/plato_cave/connections?top=1").json()[0]
    rel_id = top["relation"]["id"]
    detail = client.get(f"/api/books/plato_cave/relations/{rel_id}").json()
    assert detail["source_evidence"] and detail["target_evidence"]
    assert client.get("/api/books/nope").status_code == 404
    assert client.get("/api/books/plato_cave/journey").status_code == 404  # not synthesized yet


def test_api_survives_concurrent_requests(tmp_path, monkeypatch, settings, cave):
    db = tmp_path / "demo.db"
    process_book(cave, FixtureClient(settings.demo_dir / "plato_cave.fixture.json"), Store(db), log=lambda _: None)
    monkeypatch.setenv("MOTIF_DEMO", "1")
    monkeypatch.setenv("MOTIF_DEMO_DB", str(db))
    import motif.api
    client = TestClient(importlib.reload(motif.api).app)
    urls = ["/api/books/plato_cave", "/api/books/plato_cave/connections"] * 10
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda u: client.get(u).status_code, urls))
    assert codes == [200] * len(urls)
