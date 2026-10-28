#!/usr/bin/env python3
"""Local Daymark app server with SQLite-backed accounts and sessions."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "daymark.sqlite3"
HOST, PORT = "127.0.0.1", 8000
ITERATIONS = 310_000
SESSION_SECONDS = 60 * 60 * 24 * 30


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              username TEXT PRIMARY KEY COLLATE NOCASE,
              password_hash BLOB NOT NULL,
              salt BLOB NOT NULL,
              created_at INTEGER NOT NULL,
              is_owner INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash BLOB PRIMARY KEY,
              username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
              expires_at INTEGER NOT NULL
            );
        """)


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


class Handler(BaseHTTPRequestHandler):
    server_version = "DaymarkLocal/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, status, payload, cookie=None, clear_cookie=False):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", f"daymark_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}")
        if clear_cookie:
            self.send_header("Set-Cookie", "daymark_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        self.end_headers()
        self.wfile.write(body)

    def body_json(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["daymark_session"].value
        except (KeyError, Exception):
            return None
        digest = hashlib.sha256(token.encode("ascii", "ignore")).digest()
        with connect() as db:
            row = db.execute("""SELECT u.username,u.is_owner FROM sessions s
                JOIN users u ON u.username=s.username
                WHERE s.token_hash=? AND s.expires_at>?""", (digest, int(time.time()))).fetchone()
            if row:
                return {"username": row["username"], "isOwner": bool(row["is_owner"])}
        return None

    def create_session(self, username):
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("ascii")).digest()
        with connect() as db:
            db.execute("INSERT INTO sessions(token_hash,username,expires_at) VALUES(?,?,?)",
                       (digest, username, int(time.time()) + SESSION_SECONDS))
        return token

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            if path == "/api/me":
                user = self.session()
                with connect() as db:
                    has_users = db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
                self.send_json(200, {"user": user, "hasUsers": has_users})
                return
            if path == "/api/users":
                user = self.session()
                if not user:
                    self.send_json(401, {"error": "Please log in again."}); return
                if not user["isOwner"]:
                    self.send_json(403, {"error": "Only the application owner can view users."}); return
                with connect() as db:
                    rows = db.execute("SELECT username,created_at,is_owner FROM users ORDER BY username COLLATE NOCASE").fetchall()
                self.send_json(200, {"users": [{"username": r["username"], "createdAt": r["created_at"], "isOwner": bool(r["is_owner"])} for r in rows]})
                return
            self.send_json(404, {"error": "Not found."}); return

        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (ROOT / relative).resolve()
        if ROOT not in target.parents and target != ROOT:
            self.send_error(403); return
        if not target.is_file():
            self.send_error(404); return
        data = target.read_bytes()
        content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self.body_json()
        if payload is None:
            self.send_json(400, {"error": "Invalid request."}); return
        if path in ("/api/signup", "/api/login"):
            username = str(payload.get("username", "")).strip().lower()
            password = str(payload.get("password", ""))
            if not re.fullmatch(r"[a-z0-9._-]{3,24}", username):
                self.send_json(400, {"error": "Use 3–24 characters: letters, numbers, dots, underscores, or hyphens."}); return
            if path == "/api/signup":
                if len(password) < 8:
                    self.send_json(400, {"error": "Use a password with at least 8 characters."}); return
                salt = secrets.token_bytes(16)
                hashed = password_hash(password, salt)
                try:
                    with connect() as db:
                        owner_exists = db.execute("SELECT 1 FROM users WHERE is_owner=1").fetchone()
                        db.execute("INSERT INTO users(username,password_hash,salt,created_at,is_owner) VALUES(?,?,?,?,?)",
                                   (username, hashed, salt, int(time.time() * 1000), 0 if owner_exists else 1))
                except sqlite3.IntegrityError:
                    self.send_json(409, {"error": "That username already exists. Log in or choose another username."}); return
            else:
                with connect() as db:
                    row = db.execute("SELECT username,password_hash,salt FROM users WHERE username=?", (username,)).fetchone()
                if not row:
                    self.send_json(401, {"error": "Username is incorrect. Please check it or create an account."}); return
                if not hmac.compare_digest(password_hash(password, row["salt"]), row["password_hash"]):
                    self.send_json(401, {"error": "Password is incorrect. Please try again."}); return
                username = row["username"]
            token = self.create_session(username)
            user = self.session_from_username(username)
            self.send_json(200, {"user": user}, cookie=token)
            return
        if path == "/api/logout":
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", "")); token = cookie["daymark_session"].value
                digest = hashlib.sha256(token.encode("ascii", "ignore")).digest()
                with connect() as db:
                    db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
            except Exception:
                pass
            self.send_json(200, {"ok": True}, clear_cookie=True); return
        self.send_json(404, {"error": "Not found."})

    @staticmethod
    def session_from_username(username):
        with connect() as db:
            row = db.execute("SELECT username,is_owner FROM users WHERE username=?", (username,)).fetchone()
        return {"username": row["username"], "isOwner": bool(row["is_owner"])}


if __name__ == "__main__":
    initialize()
    print(f"Daymark is running at http://{HOST}:{PORT}")
    print(f"SQLite database: {DB_PATH}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
