import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from pymongo import MongoClient
MONGO_URL = "mongodb+srv://admin:0000@cluster0.4xb40yn.mongodb.net/?appName=Cluster0"

client = MongoClient(MONGO_URL)

db = client["attendance_db"]

users = db["users"]

users.insert_one({
    "name": "test",
    "time": str(datetime.now())
})

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "attendance.db"
SESSION_COOKIE = "clubcheck_session"
KST = timezone(timedelta(hours=9))


def now_iso():
    return datetime.now(KST).isoformat(timespec="seconds")


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return salt, base64.b64encode(digest).decode("ascii")


def verify_password(password, salt, expected_hash):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_hash)


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as conn:
        conn.executescript(
            """
            create table if not exists users (
                id integer primary key autoincrement,
                username text not null unique,
                password_salt text not null,
                password_hash text not null,
                name text not null,
                student_code text not null,
                role text not null check(role in ('admin', 'member')),
                created_at text not null
            );

            create table if not exists sessions (
                id integer primary key autoincrement,
                title text not null,
                date text not null,
                is_open integer not null default 1,
                created_at text not null
            );

            create table if not exists attendance_records (
                id integer primary key autoincrement,
                session_id integer not null,
                user_id integer not null,
                status text not null check(status in ('present', 'late', 'absent')),
                memo text not null default '',
                updated_at text not null,
                unique(session_id, user_id),
                foreign key(session_id) references sessions(id),
                foreign key(user_id) references users(id)
            );

            create table if not exists login_sessions (
                token text primary key,
                user_id integer not null,
                expires_at text not null,
                foreign key(user_id) references users(id)
            );
            """
        )

        admin = conn.execute("select id from users where role = 'admin' limit 1").fetchone()
        if not admin:
            salt, password_hash = hash_password("admin1234")
            conn.execute(
                """
                insert into users (username, password_salt, password_hash, name, student_code, role, created_at)
                values (?, ?, ?, ?, ?, 'admin', ?)
                """,
                ("admin", salt, password_hash, "관리자", "MASTER", now_iso()),
            )


def create_login_session(user_id):
    token = secrets.token_hex(24)
    expires_at = (datetime.now(KST) + timedelta(days=7)).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            "insert into login_sessions (token, user_id, expires_at) values (?, ?, ?)",
            (token, user_id, expires_at),
        )
    return token


def remove_login_session(token):
    if not token:
        return
    with db() as conn:
        conn.execute("delete from login_sessions where token = ?", (token,))


def get_user_by_session(token):
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            """
            select users.id, users.username, users.name, users.student_code, users.role
            from login_sessions
            join users on users.id = login_sessions.user_id
            where login_sessions.token = ?
              and login_sessions.expires_at > ?
            """,
            (token, now_iso()),
        ).fetchone()
    return dict(row) if row else None


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            return self.serve_file("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.serve_file("app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self.serve_file("styles.css", "text/css; charset=utf-8")
        if path == "/api/session":
            return self.json_response({"user": self.current_user()})
        if path == "/api/admin/dashboard":
            return self.admin_dashboard()
        if path == "/api/member/dashboard":
            return self.member_dashboard()
        if path.startswith("/api/admin/sessions/") and path.endswith("/export"):
            session_id = path.split("/")[-2]
            return self.export_session_csv(session_id)
        if path == "/api/admin/reports/member-slides":
            return self.export_member_slides()

        return self.json_response({"error": "찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/login":
            return self.login()
        if path == "/api/logout":
            return self.logout()
        if path == "/api/admin/sessions":
            return self.create_session()
        if path == "/api/admin/members":
            return self.create_member()
        if path == "/api/admin/admins":
            return self.create_admin()
        if path.startswith("/api/admin/sessions/") and path.endswith("/toggle"):
            session_id = path.split("/")[-2]
            return self.toggle_session(session_id)
        if path.startswith("/api/admin/sessions/") and path.endswith("/update"):
            session_id = path.split("/")[-2]
            return self.update_session(session_id)
        if path.startswith("/api/admin/sessions/") and path.endswith("/delete"):
            session_id = path.split("/")[-2]
            return self.delete_session(session_id)
        if path.startswith("/api/admin/members/") and path.endswith("/password"):
            member_id = path.split("/")[-2]
            return self.reset_member_password(member_id)
        if path.startswith("/api/admin/members/") and path.endswith("/update"):
            member_id = path.split("/")[-2]
            return self.update_member(member_id)
        if path.startswith("/api/admin/members/") and path.endswith("/delete"):
            member_id = path.split("/")[-2]
            return self.delete_member(member_id)
        if path.startswith("/api/admin/admins/") and path.endswith("/delete"):
            admin_id = path.split("/")[-2]
            return self.delete_admin(admin_id)
        if path == "/api/admin/change-password":
            return self.change_admin_password()
        if path == "/api/member/attendance":
            return self.submit_attendance()
        if path == "/api/member/attendance/delete":
            return self.delete_attendance()

        return self.json_response({"error": "찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)

    def serve_file(self, filename, content_type):
        target = ROOT / filename
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def parse_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def current_user(self):
        cookies = SimpleCookie(self.headers.get("Cookie"))
        token = cookies.get(SESSION_COOKIE)
        return get_user_by_session(token.value if token else None)

    def require_role(self, role):
        user = self.current_user()
        if not user or user["role"] != role:
            self.json_response({"error": "권한이 없습니다."}, status=HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def login(self):
        payload = self.parse_json()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        with db() as conn:
            row = conn.execute("select * from users where username = ?", (username,)).fetchone()

        if not row or not verify_password(password, row["password_salt"], row["password_hash"]):
            return self.json_response({"error": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=HTTPStatus.UNAUTHORIZED)

        token = create_login_session(row["id"])
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "user": {
                        "id": row["id"],
                        "username": row["username"],
                        "name": row["name"],
                        "student_code": row["student_code"],
                        "role": row["role"],
                    }
                },
                ensure_ascii=False,
            ).encode("utf-8")
        )

    def logout(self):
        cookies = SimpleCookie(self.headers.get("Cookie"))
        token = cookies.get(SESSION_COOKIE)
        if token:
            remove_login_session(token.value)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Set-Cookie", f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def create_session(self):
        user = self.require_role("admin")
        if not user:
            return
        payload = self.parse_json()
        title = payload.get("title", "").strip()
        date = payload.get("date", "").strip()
        if not title or not date:
            return self.json_response({"error": "세션 이름과 날짜가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            conn.execute(
                "insert into sessions (title, date, is_open, created_at) values (?, ?, 1, ?)",
                (title, date, now_iso()),
            )
        self.json_response({"ok": True})

    def toggle_session(self, session_id):
        user = self.require_role("admin")
        if not user:
            return

        with db() as conn:
            row = conn.execute("select is_open from sessions where id = ?", (session_id,)).fetchone()
            if not row:
                return self.json_response({"error": "세션을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            next_value = 0 if row["is_open"] else 1
            conn.execute("update sessions set is_open = ? where id = ?", (next_value, session_id))
        self.json_response({"ok": True})

    def update_session(self, session_id):
        user = self.require_role("admin")
        if not user:
            return
        payload = self.parse_json()
        title = payload.get("title", "").strip()
        date = payload.get("date", "").strip()
        if not title or not date:
            return self.json_response({"error": "세션 이름과 날짜가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            row = conn.execute("select id from sessions where id = ?", (session_id,)).fetchone()
            if not row:
                return self.json_response({"error": "세션을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            conn.execute("update sessions set title = ?, date = ? where id = ?", (title, date, session_id))
        self.json_response({"ok": True})

    def delete_session(self, session_id):
        user = self.require_role("admin")
        if not user:
            return

        with db() as conn:
            row = conn.execute("select id from sessions where id = ?", (session_id,)).fetchone()
            if not row:
                return self.json_response({"error": "세션을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            conn.execute("delete from attendance_records where session_id = ?", (session_id,))
            conn.execute("delete from sessions where id = ?", (session_id,))
        self.json_response({"ok": True})

    def create_member(self):
        user = self.require_role("admin")
        if not user:
            return

        payload = self.parse_json()
        name = payload.get("name", "").strip()
        student_code = payload.get("student_code", "").strip()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")

        if not all([name, student_code, username, password]):
            return self.json_response({"error": "모든 회원 정보가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        salt, password_hash = hash_password(password)
        try:
            with db() as conn:
                conn.execute(
                    """
                    insert into users (username, password_salt, password_hash, name, student_code, role, created_at)
                    values (?, ?, ?, ?, ?, 'member', ?)
                    """,
                    (username, salt, password_hash, name, student_code, now_iso()),
                )
        except sqlite3.IntegrityError:
            return self.json_response({"error": "이미 사용 중인 아이디입니다."}, status=HTTPStatus.BAD_REQUEST)

        self.json_response({"ok": True})

    def create_admin(self):
        user = self.require_role("admin")
        if not user:
            return

        payload = self.parse_json()
        name = payload.get("name", "").strip()
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
        if not all([name, username, password]):
            return self.json_response({"error": "이름, 아이디, 비밀번호가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        salt, password_hash = hash_password(password)
        try:
            with db() as conn:
                conn.execute(
                    """
                    insert into users (username, password_salt, password_hash, name, student_code, role, created_at)
                    values (?, ?, ?, ?, 'ADMIN', 'admin', ?)
                    """,
                    (username, salt, password_hash, name, now_iso()),
                )
        except sqlite3.IntegrityError:
            return self.json_response({"error": "이미 사용 중인 아이디입니다."}, status=HTTPStatus.BAD_REQUEST)
        self.json_response({"ok": True})

    def delete_admin(self, admin_id):
        user = self.require_role("admin")
        if not user:
            return
        if str(user["id"]) == str(admin_id):
            return self.json_response({"error": "현재 로그인한 관리자 자신은 삭제할 수 없습니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            target = conn.execute("select id from users where id = ? and role = 'admin'", (admin_id,)).fetchone()
            if not target:
                return self.json_response({"error": "관리자 계정을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            admin_count = conn.execute("select count(*) as c from users where role = 'admin'").fetchone()["c"]
            if admin_count <= 1:
                return self.json_response({"error": "관리자는 최소 1명 이상 있어야 합니다."}, status=HTTPStatus.BAD_REQUEST)
            conn.execute("delete from login_sessions where user_id = ?", (admin_id,))
            conn.execute("delete from users where id = ? and role = 'admin'", (admin_id,))
        self.json_response({"ok": True})

    def reset_member_password(self, member_id):
        user = self.require_role("admin")
        if not user:
            return

        payload = self.parse_json()
        password = payload.get("password", "")
        if not password:
            return self.json_response({"error": "새 비밀번호를 입력하세요."}, status=HTTPStatus.BAD_REQUEST)

        salt, password_hash = hash_password(password)
        with db() as conn:
            conn.execute(
                "update users set password_salt = ?, password_hash = ? where id = ? and role = 'member'",
                (salt, password_hash, member_id),
            )
        self.json_response({"ok": True})

    def update_member(self, member_id):
        user = self.require_role("admin")
        if not user:
            return

        payload = self.parse_json()
        name = payload.get("name", "").strip()
        student_code = payload.get("student_code", "").strip()
        username = payload.get("username", "").strip()
        if not all([name, student_code, username]):
            return self.json_response({"error": "이름, 학번/기수, 아이디가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        try:
            with db() as conn:
                row = conn.execute("select id from users where id = ? and role = 'member'", (member_id,)).fetchone()
                if not row:
                    return self.json_response({"error": "회원을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
                conn.execute(
                    "update users set name = ?, student_code = ?, username = ? where id = ? and role = 'member'",
                    (name, student_code, username, member_id),
                )
        except sqlite3.IntegrityError:
            return self.json_response({"error": "이미 사용 중인 아이디입니다."}, status=HTTPStatus.BAD_REQUEST)
        self.json_response({"ok": True})

    def delete_member(self, member_id):
        user = self.require_role("admin")
        if not user:
            return

        with db() as conn:
            row = conn.execute("select id from users where id = ? and role = 'member'", (member_id,)).fetchone()
            if not row:
                return self.json_response({"error": "회원을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            conn.execute("delete from attendance_records where user_id = ?", (member_id,))
            conn.execute("delete from login_sessions where user_id = ?", (member_id,))
            conn.execute("delete from users where id = ? and role = 'member'", (member_id,))
        self.json_response({"ok": True})

    def change_admin_password(self):
        user = self.require_role("admin")
        if not user:
            return

        payload = self.parse_json()
        current_password = payload.get("current_password", "")
        new_password = payload.get("new_password", "")
        if not current_password or not new_password:
            return self.json_response({"error": "현재 비밀번호와 새 비밀번호를 입력하세요."}, status=HTTPStatus.BAD_REQUEST)
        if len(new_password) < 4:
            return self.json_response({"error": "새 비밀번호는 4자 이상이어야 합니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            row = conn.execute("select id, password_salt, password_hash from users where id = ? and role = 'admin'", (user["id"],)).fetchone()
            if not row:
                return self.json_response({"error": "관리자 계정을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            if not verify_password(current_password, row["password_salt"], row["password_hash"]):
                return self.json_response({"error": "현재 비밀번호가 일치하지 않습니다."}, status=HTTPStatus.BAD_REQUEST)

            salt, password_hash = hash_password(new_password)
            conn.execute(
                "update users set password_salt = ?, password_hash = ? where id = ?",
                (salt, password_hash, user["id"]),
            )
        self.json_response({"ok": True})

    def submit_attendance(self):
        user = self.require_role("member")
        if not user:
            return

        payload = self.parse_json()
        session_id = payload.get("session_id")
        status = payload.get("status")
        memo = payload.get("memo", "").strip()
        if status not in {"present", "late", "absent"}:
            return self.json_response({"error": "올바른 출결 상태가 아닙니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            session = conn.execute("select * from sessions where id = ?", (session_id,)).fetchone()
            if not session or not session["is_open"]:
                return self.json_response({"error": "현재 작성할 수 없는 세션입니다."}, status=HTTPStatus.BAD_REQUEST)

            conn.execute(
                """
                insert into attendance_records (session_id, user_id, status, memo, updated_at)
                values (?, ?, ?, ?, ?)
                on conflict(session_id, user_id) do update set
                    status = excluded.status,
                    memo = excluded.memo,
                    updated_at = excluded.updated_at
                """,
                (session_id, user["id"], status, memo, now_iso()),
            )
        self.json_response({"ok": True})

    def delete_attendance(self):
        user = self.require_role("member")
        if not user:
            return

        payload = self.parse_json()
        session_id = payload.get("session_id")
        if not session_id:
            return self.json_response({"error": "세션 정보가 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            session = conn.execute("select id, is_open from sessions where id = ?", (session_id,)).fetchone()
            if not session:
                return self.json_response({"error": "세션을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)
            if not session["is_open"]:
                return self.json_response({"error": "마감된 세션 기록은 삭제할 수 없습니다."}, status=HTTPStatus.BAD_REQUEST)

            conn.execute(
                "delete from attendance_records where session_id = ? and user_id = ?",
                (session_id, user["id"]),
            )
        self.json_response({"ok": True})

    def admin_dashboard(self):
        user = self.require_role("admin")
        if not user:
            return

        with db() as conn:
            members = [
                dict(row)
                for row in conn.execute(
                    "select id, username, name, student_code from users where role = 'member' order by created_at desc"
                ).fetchall()
            ]
            admins = [
                dict(row)
                for row in conn.execute(
                    "select id, username, name from users where role = 'admin' order by created_at asc"
                ).fetchall()
            ]

            sessions = []
            session_rows = conn.execute(
                "select id, title, date, is_open from sessions order by date desc, id desc"
            ).fetchall()
            for session in session_rows:
                records = [
                    dict(row)
                    for row in conn.execute(
                        """
                        select attendance_records.status, attendance_records.memo, users.name, users.student_code
                        from attendance_records
                        join users on users.id = attendance_records.user_id
                        where attendance_records.session_id = ?
                        order by users.name asc
                        """,
                        (session["id"],),
                    ).fetchall()
                ]
                sessions.append(
                    {
                        "id": session["id"],
                        "title": session["title"],
                        "date": session["date"],
                        "is_open": bool(session["is_open"]),
                        "record_count": len(records),
                        "late_count": sum(1 for r in records if r["status"] == "late"),
                        "absent_count": sum(1 for r in records if r["status"] == "absent"),
                        "records": records,
                    }
                )

        self.json_response({"members": members, "admins": admins, "sessions": sessions})

    def member_dashboard(self):
        user = self.require_role("member")
        if not user:
            return

        with db() as conn:
            open_sessions = []
            session_rows = conn.execute(
                """
                select sessions.id, sessions.title, sessions.date
                from sessions
                where sessions.is_open = 1
                order by sessions.date asc, sessions.id asc
                """
            ).fetchall()

            for session in session_rows:
                record = conn.execute(
                    """
                    select status, memo
                    from attendance_records
                    where session_id = ? and user_id = ?
                    """,
                    (session["id"], user["id"]),
                ).fetchone()
                if not record:
                    open_sessions.append(dict(session))

            history = [
                dict(row)
                for row in conn.execute(
                    """
                    select
                        sessions.id as session_id,
                        sessions.title,
                        sessions.date,
                        sessions.is_open,
                        attendance_records.status,
                        attendance_records.memo
                    from attendance_records
                    join sessions on sessions.id = attendance_records.session_id
                    where attendance_records.user_id = ?
                    order by sessions.date asc, attendance_records.updated_at asc
                    """,
                    (user["id"],),
                ).fetchall()
            ]

        self.json_response({"open_sessions": open_sessions, "history": history})

    def export_session_csv(self, session_id):
        user = self.require_role("admin")
        if not user:
            return

        with db() as conn:
            session = conn.execute("select title, date from sessions where id = ?", (session_id,)).fetchone()
            if not session:
                return self.json_response({"error": "세션을 찾을 수 없습니다."}, status=HTTPStatus.NOT_FOUND)

            rows = conn.execute(
                """
                select users.name, users.student_code, users.username, attendance_records.status, attendance_records.memo
                from attendance_records
                join users on users.id = attendance_records.user_id
                where attendance_records.session_id = ?
                order by users.name asc
                """,
                (session_id,),
            ).fetchall()

        header = [["세션", "날짜", "이름", "학번/기수", "아이디", "상태", "메모"]]
        for row in rows:
            header.append(
                [
                    session["title"],
                    session["date"],
                    row["name"],
                    row["student_code"],
                    row["username"],
                    {"present": "출석", "late": "지각", "absent": "결석"}[row["status"]],
                    row["memo"],
                ]
            )

        payload = ("\ufeff" + "\n".join(",".join(csv_escape(value) for value in line) for line in header)).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=attendance-{session['date']}.csv")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def export_member_slides(self):
        user = self.require_role("admin")
        if not user:
            return

        params = urlparse(self.path).query
        query = {}
        for pair in params.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                query[k] = v
        date_from = query.get("from", "").strip()
        date_to = query.get("to", "").strip()
        if not date_from or not date_to:
            return self.json_response({"error": "기간 시작일과 종료일이 필요합니다."}, status=HTTPStatus.BAD_REQUEST)

        with db() as conn:
            members = conn.execute(
                """
                select id, name, student_code, username
                from users
                where role = 'member'
                order by name asc
                """
            ).fetchall()

            sections = []
            for member in members:
                rows = conn.execute(
                    """
                    select sessions.title, sessions.date, attendance_records.status, attendance_records.memo
                    from attendance_records
                    join sessions on sessions.id = attendance_records.session_id
                    where attendance_records.user_id = ?
                      and sessions.date >= ?
                      and sessions.date <= ?
                    order by sessions.date asc
                    """,
                    (member["id"], date_from, date_to),
                ).fetchall()

                present_count = sum(1 for r in rows if r["status"] == "present")
                late_count = sum(1 for r in rows if r["status"] == "late")
                absent_count = sum(1 for r in rows if r["status"] == "absent")

                row_html = "".join(
                    f"<tr><td>{escape_html(r['date'])}</td><td>{escape_html(r['title'])}</td><td>{status_label(r['status'])}</td><td>{escape_html(r['memo'] or '')}</td></tr>"
                    for r in rows
                )
                if not row_html:
                    row_html = "<tr><td colspan='4'>기록 없음</td></tr>"

                sections.append(
                    f"""
                    <section class="slide">
                      <h2>{escape_html(member['name'])}</h2>
                      <p>{escape_html(member['student_code'])} · {escape_html(member['username'])}</p>
                      <p>출석 {present_count} / 지각 {late_count} / 결석 {absent_count}</p>
                      <table>
                        <thead><tr><th>날짜</th><th>세션</th><th>상태</th><th>메모</th></tr></thead>
                        <tbody>{row_html}</tbody>
                      </table>
                    </section>
                    """
                )

        html = f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>회원별 출결 슬라이드</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 0; background: #f4f7fb; }}
    .slide {{ page-break-after: always; min-height: 100vh; box-sizing: border-box; padding: 40px; background: #fff; margin: 16px; border-radius: 12px; }}
    h1 {{ margin: 0 0 12px; }}
    h2 {{ margin: 0 0 8px; }}
    p {{ margin: 0 0 10px; color: #445; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ccd5e2; padding: 8px; text-align: left; font-size: 14px; }}
    thead {{ background: #eef3fb; }}
  </style>
</head>
<body>
  <section class="slide">
    <h1>회원별 출결 슬라이드</h1>
    <p>기간: {escape_html(date_from)} ~ {escape_html(date_to)}</p>
    <p>각 페이지가 한 명의 출결 보고서입니다.</p>
  </section>
  {''.join(sections)}
</body>
</html>
"""
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=member-slides-{date_from}-{date_to}.html")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def json_response(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def csv_escape(value):
    text = str(value).replace('"', '""')
    return f'"{text}"'


def escape_html(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def status_label(status):
    return {"present": "출석", "late": "지각", "absent": "결석"}.get(status, "미제출")


def main():
    init_db()
    port = int(os.environ.get("PORT", "8010"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Club Check server running on http://0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
