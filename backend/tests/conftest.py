import pytest

from motif.config import load_settings
from motif.llm import FixtureClient
from motif.pipeline import process_book
from motif.store import Store
from motif.text import load_book


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture(scope="session")
def cave(settings):
    return load_book(settings.texts_dir, "plato_cave")


@pytest.fixture()
def demo_store(settings, cave):
    store = Store(":memory:")
    client = FixtureClient(settings.demo_dir / "plato_cave.fixture.json")
    reports = process_book(cave, client, store, log=lambda _: None)
    store.reports = reports
    return store
