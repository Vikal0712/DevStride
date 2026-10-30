import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import database
from app.main import app, COOKIE, token_digest
from app.models import Base, SessionRecord

@pytest.fixture()
def client(monkeypatch):
    handle, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(handle)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def sqlite_fk(connection, _): connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    with TestClient(app) as c:
        c.headers.update({"Origin":"http://localhost:5173", "X-Requested-With":"XMLHttpRequest"})
        yield c
    Base.metadata.drop_all(engine)
    engine.dispose()
    os.unlink(path)

def register(client, username, email):
    return client.post("/api/auth/register", json={"full_name":username.title(),"username":username,"email":email,"password":"Long-safe-pass-123"})
