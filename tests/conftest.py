import pytest

from domain_guard.classifier import DomainGuardFilter


@pytest.fixture(scope="session")
def guard():
    return DomainGuardFilter()
