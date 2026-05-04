from __future__ import annotations

import pytest

from app.database import Base

from .support import TestingSessionLocal, create_user, engine


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def novels_api():
    from app.api import novels as novels_api

    return novels_api


@pytest.fixture
def active_user(db):
    return create_user(db)


@pytest.fixture
def sql_engine():
    return engine
