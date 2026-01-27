from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.config import settings

# Hash de senha seguro e compatível no Windows (sem bcrypt)
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    """
    Gera hash seguro da senha.
    """
    if not password or len(password) < 6:
        raise ValueError("Senha deve ter no mínimo 6 caracteres.")
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica senha informada contra o hash salvo.
    """
    if not password or not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, email: str) -> str:
    """
    Cria JWT de acesso.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_exp_minutes)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return token


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica e valida JWT.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.PyJWTError:
        return None
