from datetime import datetime, timedelta
from jose import jwt, JWTError
from config.settings import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS


def create_token(user_id: int, role: str = "user", username: str = "") -> str:
    expire = datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {"user_id": user_id, "role": role, "username": username, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
