"""Auth helpers: JWT creation/decoding, bcrypt hashing, FastAPI dependencies.

All secrets and algorithm choices come from SETTINGS — never hardcoded.
"""

import bcrypt
import jwt
from fastapi import Header, HTTPException

from backend.config import SETTINGS


SUPER_ADMIN_ROLE_CANONICAL = "Super-Admin"


def create_access_token(subject_id: int, username: str, role: str) -> str:
    """Encode a JWT containing {id, username, role}.

    The role is stored as-is; consumers must compare case-insensitively.
    """
    payload = {"id": subject_id, "username": username, "role": role}
    return jwt.encode(
        payload,
        SETTINGS.jwt_secret,
        algorithm=SETTINGS.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Decode a JWT and return its payload dict.

    Raises HTTPException(401) if the token is expired, malformed, or
    fails signature verification.
    """
    try:
        return jwt.decode(
            token,
            SETTINGS.jwt_secret,
            algorithms=[SETTINGS.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Login session expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid login token.")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password (as UTF-8 str)."""
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt password check."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Extract {name, role} from a Bearer JWT in the Authorization header.

    Compatible with FastAPI as a dependency, and callable directly with a
    raw header string (matches the legacy signature in ingestion/api.py).
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required.",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header.",
        )

    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)

    role = payload.get("role") or "Viewer"
    username = payload.get("username") or payload.get("name") or "user"

    return {"name": username, "role": role}


def require_super_admin(
    authorization: str | None = Header(default=None),
) -> dict:
    """Require the caller to have the Super-Admin role.

    Role comparison is case-insensitive so 'Super-Admin', 'super-admin',
    and 'SUPER-ADMIN' all pass.
    """
    user = get_current_user(authorization)
    if str(user.get("role") or "").strip().lower() != "super-admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super-Admin can execute actions.",
        )
    return user


if __name__ == "__main__":
    # Smoke test — run with: python -m backend.security
    token = create_access_token(1, "alice", "Super-Admin")
    decoded = decode_token(token)
    assert decoded["username"] == "alice"
    assert decoded["role"] == "Super-Admin"

    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False

    # Header-based auth flows
    assert get_current_user(f"Bearer {token}")["name"] == "alice"
    assert require_super_admin(f"Bearer {token}")["role"] == "Super-Admin"

    # Case-insensitive super-admin check
    lower_token = create_access_token(2, "bob", "super-admin")
    assert require_super_admin(f"Bearer {lower_token}")["name"] == "bob"

    # Missing / bad headers raise 401
    try:
        get_current_user(None)
        raise SystemExit("expected 401 for missing header")
    except HTTPException as exc:
        assert exc.status_code == 401

    # Viewer is rejected by super-admin gate
    viewer_token = create_access_token(3, "carol", "Viewer")
    try:
        require_super_admin(f"Bearer {viewer_token}")
        raise SystemExit("expected 403 for Viewer")
    except HTTPException as exc:
        assert exc.status_code == 403

    print("security.py smoke test: OK")
