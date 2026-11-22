from pathlib import Path

import pytest

TEST_DATA = Path.home() / ".cache" / "skywall-test-data"


@pytest.fixture(scope="session")
def data():
    from skywall.catalog import ensure_data
    ensure_data(TEST_DATA)
    return TEST_DATA
