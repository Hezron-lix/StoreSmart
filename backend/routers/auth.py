"""Auth router: signup and login endpoints.

Endpoints moved from ingestion/api.py. Behavior is identical except:
- The old code registered each endpoint twice, once at /auth/* and once
  at /api/auth/*. This router keeps only /api/auth/* (the router prefix),
  because the current frontend only calls /api/auth/*.
"""

from fastapi import APIRouter, HTTPException

from backend.db import get_connection
from backend.models import LoginRequest, SignupRequest
from backend.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
def auth_signup(req: SignupRequest):
    username = req.username.strip()
    role = req.role.strip()
    if not username or not req.password:
        raise HTTPException(status_code=400, detail="Username and password required")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="User already exists")

        pw_hash = hash_password(req.password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, pw_hash, role),
        )
        conn.commit()
        user_id = cursor.lastrowid
        user_obj = {"id": user_id, "username": username, "role": role}
        token = create_access_token(user_id, username, role)
        return {"message": "Account created", "user": user_obj, "token": token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Signup failed: {exc}")
    finally:
        if conn:
            conn.close()


@router.post("/login")
def auth_login(req: LoginRequest):
    username = req.username.strip()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        if not verify_password(req.password, str(row["password_hash"])):
            raise HTTPException(status_code=401, detail="Incorrect password")

        user_obj = {"id": row["id"], "username": row["username"], "role": row["role"]}
        token = create_access_token(row["id"], row["username"], row["role"])
        return {"message": "Login successful", "user": user_obj, "token": token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}")
    finally:
        if conn:
            conn.close()
