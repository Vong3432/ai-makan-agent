import pytest

from makan.config import get_settings


@pytest.fixture(autouse=True)
def _dev_settings(monkeypatch: pytest.MonkeyPatch):
    """Tests run in dev-auth mode with no real secrets."""
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
