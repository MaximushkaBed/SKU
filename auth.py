from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import hashlib
import bcrypt
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRoleEnum
from schemas import Token, UserCreate, UserRead


SECRET_KEY = "CHANGE_ME_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

DBSession = Annotated[Session, Depends(get_db)]


def _to_bcrypt_input(password: str) -> bytes:
    """Преобразуем пароль в <=72 байт для bcrypt. SHA256 даёт 32 байта — без ограничений по длине."""
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) <= 72:
        return pwd_bytes
    return hashlib.sha256(pwd_bytes).digest()  # 32 байта


def get_password_hash(password: str) -> str:
    pwd = _to_bcrypt_input(password)
    return bcrypt.hashpw(pwd, bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd = _to_bcrypt_input(plain_password)
    return bcrypt.checkpw(pwd, hashed_password.encode("ascii"))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.status:
        return None
    return user


async def get_current_user(db: DBSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if user_id is None or role is None:
            raise credentials_exception
        user_id = int(user_id) if not isinstance(user_id, int) else user_id
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.status:
        raise credentials_exception
    return user


def require_role(*roles: str):
    async def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return current_user

    return dependency


async def register_user(user_in: UserCreate, db: DBSession) -> UserRead:
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    role_val = (user_in.role or UserRoleEnum.STUDENT)
    if role_val in ("admin", "teacher"):
        raise HTTPException(
            status_code=403,
            detail="Регистрация доступна только с ролью студента. Роли преподавателя и администратора назначаются отдельно.",
        )
    if isinstance(role_val, UserRoleEnum):
        role_val = role_val.value
    db_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=role_val,
        status=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return UserRead.model_validate(db_user)


async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession
) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return Token(access_token=access_token)

