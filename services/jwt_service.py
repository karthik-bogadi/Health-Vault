"""
JWT (JSON Web Token) service for HealthVault role-based authentication.

WHAT IS JWT?
------------
A JWT is a compact, signed string that proves a user is authenticated.
It has three parts separated by dots:  header.payload.signature

  - Header  : algorithm info (we use HS256 = HMAC-SHA256)
  - Payload : claims — data about the user (id, role, expiry time, etc.)
  - Signature: proves the token was issued by our server and was not tampered with

WHY USE JWT HERE?
-----------------
After a doctor or admin logs in with email + password, we create a JWT and store
it in the Flask session cookie. On every protected page request we read the token
from the session, verify its signature and expiry, and check the user's role.

FLOW
----
  1. User submits login form  →  server checks password hash in SQLite
  2. Server calls create_token()  →  returns signed JWT string
  3. JWT stored in session["jwt_token"]
  4. Protected route calls verify_token(session["jwt_token"])
  5. If valid and role matches  →  allow access; otherwise redirect to login

DEPENDENCY
----------
PyJWT  —  pip install PyJWT
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Secret key used to sign tokens. In production, set JWT_SECRET_KEY in .env
# to a long random string (different from Flask's SECRET_KEY).
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY", "dev-jwt-secret-change-me")

# HS256 is a symmetric algorithm: the same secret signs AND verifies the token.
JWT_ALGORITHM = "HS256"

# Tokens expire after this many hours. Shorter = more secure; longer = fewer re-logins.
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_token(
    user_id: int,
    role: str,
    email: str,
    name: str,
) -> str:
    """
    Build and sign a JWT for a successfully authenticated user.

    Parameters
    ----------
    user_id : int
        Primary key from the `doctors` or `admins` table.
    role : str
        Either "doctor" or "admin". Used by route guards to enforce access.
    email : str
        Stored in the token so we can display it without a DB lookup.
    name : str
        Display name for the logged-in user.

    Returns
    -------
    str
        Encoded JWT string ready to store in session["jwt_token"].
    """
    now = datetime.now(timezone.utc)

    # The "payload" (claims) is a plain Python dict that gets JSON-encoded
    # inside the token. Never put passwords or secrets here — anyone who
    # decodes the token (without verifying) can read the payload.
    payload: dict[str, Any] = {
        # PyJWT requires "sub" (subject) to be a string, not an integer.
        # We store the DB primary key as a string and cast back to int when needed.
        "sub": str(user_id),
        "role": role,            # custom claim: which role this token grants
        "email": email,
        "name": name,
        "iat": now,              # "issued at" — when the token was created
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),  # expiry — PyJWT rejects expired tokens automatically
    }

    # jwt.encode() serialises the payload, signs it, and returns a string like:
    #   eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjF9.xxxxx
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # PyJWT >= 2.x returns str; older versions returned bytes — normalise to str.
    return token if isinstance(token, str) else token.decode("utf-8")


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def verify_token(token: str | None) -> dict[str, Any] | None:
    """
    Decode and validate a JWT.

    Returns the payload dict if the token is valid and not expired,
    or None if the token is missing, malformed, expired, or tampered with.

    WHY RETURN None INSTEAD OF RAISING?
    -----------------------------------
    Route handlers can simply check `if payload is None` and redirect to login
    without needing try/except blocks everywhere.
    """
    if not token:
        return None

    try:
        # jwt.decode() verifies the signature AND checks the exp claim.
        # If anything is wrong it raises jwt.PyJWTError (or a subclass).
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        return payload

    except jwt.ExpiredSignatureError:
        # Token was valid but has passed its expiry time.
        return None

    except jwt.InvalidTokenError:
        # Covers bad signature, malformed token, wrong algorithm, etc.
        return None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def get_current_user_from_session(session) -> dict[str, Any] | None:
    """
    Read jwt_token from the Flask session, verify it, and return the payload.

    Usage in a route:
        user = get_current_user_from_session(session)
        if not user or user.get("role") != "doctor":
            return redirect(url_for("doctor_login"))
    """
    return verify_token(session.get("jwt_token"))


def clear_auth_session(session) -> None:
    """
    Remove JWT-related keys from the Flask session on logout.

    We only remove auth keys — not patient session keys like patient_id,
    so a doctor logout does not accidentally log out a patient (and vice versa).
    """
    session.pop("jwt_token", None)
    session.pop("auth_role", None)
    session.pop("auth_name", None)


def store_token_in_session(session, token: str, role: str, name: str) -> None:
    """
    Persist the JWT and a few display fields in the Flask session cookie.

    Flask serialises the session dict, signs it with SECRET_KEY, and sends
    it back to the browser as an HttpOnly cookie on every response.
    """
    session["jwt_token"] = token
    session["auth_role"] = role
    session["auth_name"] = name
