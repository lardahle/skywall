from pathlib import Path

import pytest

TEST_DATA = Path.home() / ".cache" / "skywall-test-data"


@pytest.fixture(scope="session")
def data():
    from skywall.catalog import ensure_data
    ensure_data(TEST_DATA)
    return TEST_DATA


class FakeRunner:
    """Records argv lists; answers `gsettings get <schema> <key>` from a dict."""

    def __init__(self, gsettings_values: dict[str, str] | None = None):
        self.values = dict(gsettings_values or {})
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(list(cmd))
        if cmd[:2] == ["gsettings", "get"]:
            return self.values.get(cmd[3], "''") + "\n"
        return ""
