"""Shared pytest fixtures for CivicFork backend tests."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.session import session_store


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure session store is empty before each test."""
    session_store.clear()
    yield
    session_store.clear()


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client
