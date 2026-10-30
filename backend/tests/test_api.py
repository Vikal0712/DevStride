from datetime import datetime, timezone, timedelta
from app import database
from app.main import token_digest
from app.models import SessionRecord
from conftest import register

def test_registration_duplicate_login_logout_and_session_expiry(client):
    first=register(client,"alpha","alpha@example.com")
    assert first.status_code==201
    assert first.json()["is_admin"] is True
    assert client.get("/api/admin/overview").json()["total_users"]==1
    assert "password_hash" not in first.json()
    assert register(client,"alpha","other@example.com").status_code==409
    assert client.post("/api/auth/login",json={"identity":"alpha","password":"wrong-password"}).status_code==401
    assert client.get("/api/auth/me").status_code==200
    token=client.cookies.get("devstride_session")
    with database.SessionLocal() as db:
        session=db.get(SessionRecord,token_digest(token)); session.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1); db.commit()
    assert client.get("/api/auth/me").status_code==401
    assert client.post("/api/auth/login",json={"identity":"alpha@example.com","password":"Long-safe-pass-123"}).status_code==200
    assert client.post("/api/auth/logout").status_code==204
    assert client.get("/api/auth/me").status_code==401

def test_activity_timestamps_and_users_cannot_read_edit_or_delete_each_other(client):
    assert register(client,"alpha","alpha@example.com").status_code==201
    created=client.post("/api/activities",json={"title":"A private task","category":"Coding","priority":"High","due_date":"2026-10-30"})
    assert created.status_code==201
    activity_id=created.json()["id"]
    completed=client.patch(f"/api/activities/{activity_id}/complete",json={"is_completed":True})
    assert completed.status_code==200 and completed.json()["completed_at"]
    analytics=client.get("/api/analytics/weekly").json()
    assert analytics["summary"]["completed_today"]==1
    assert analytics["recent_activity"][0]["title"]=="A private task"
    assert client.patch(f"/api/activities/{activity_id}/complete",json={"is_completed":False}).json()["completed_at"] is None
    client.post("/api/auth/logout")
    second=register(client,"bravo","bravo@example.com")
    assert second.status_code==201
    assert second.json()["is_admin"] is False
    assert client.get("/api/admin/overview").status_code==403
    assert client.get(f"/api/activities/{activity_id}").status_code==404
    assert client.put(f"/api/activities/{activity_id}",json={"title":"Hijack","category":"Coding","priority":"Low"}).status_code==404
    assert client.delete(f"/api/activities/{activity_id}").status_code==404
    assert client.get("/api/activities").json()["items"]==[]

def test_coding_question_count_and_per_user_progress(client):
    assert register(client,"alpha","alpha@example.com").status_code==201
    questions=client.get("/api/coding/questions").json()
    assert len(questions)==45
    question_id=questions[0]["id"]
    assert client.put(f"/api/coding/progress/{question_id}",json={"is_solved":True,"personal_notes":"Reviewed complexity"}).status_code==200
    assert len(client.get("/api/coding/progress").json())==1
    client.post("/api/auth/logout")
    assert register(client,"bravo","bravo@example.com").status_code==201
    assert client.get("/api/coding/progress").json()==[]
    assert client.put(f"/api/coding/progress/{question_id}",json={"is_solved":False,"personal_notes":""}).status_code==200

def test_mutations_require_valid_origin(client):
    client.headers.pop("Origin")
    response=client.post("/api/auth/register",json={"full_name":"X","username":"alpha","email":"alpha@example.com","password":"Long-safe-pass-123"})
    assert response.status_code==403

def test_account_deletion_removes_private_data(client):
    assert register(client,"alpha","alpha@example.com").status_code==201
    client.post("/api/activities",json={"title":"Remove with account","category":"Personal","priority":"Low"})
    response=client.delete("/api/profile")
    assert response.status_code==204
    assert client.get("/api/auth/me").status_code==401
