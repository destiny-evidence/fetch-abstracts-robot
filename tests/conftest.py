import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure():
    os.environ["ENV"] = "local"
