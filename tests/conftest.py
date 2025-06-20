import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure():
    os.environ["ENV"] = "local"
    os.environ["DESTINY_REPOSITORY_URL"] = "http://localhost:8001/enhancement/"
