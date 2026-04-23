from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles

from auth import DBSession, get_current_user, get_password_hash, login_for_access_token, register_user
from database import Base, engine, ensure_sqlite_schema, SessionLocal
from models import Subject, User
from seed_tests import ensure_default_tests
from seed_demo import seed as seed_demo_students

# Предметы по умолчанию (преподаватели создают тесты только по ним)
DEFAULT_SUBJECTS = [
    "Казахский язык",
    "Английский язык",
    "Русский язык",
    "Высшая математика",
    "История Казахстана",
    "Политология",
    "Социология",
    "Анализ данных",
    "Web-программирование",
    "Языки и технологии программирования",
    "Системы управления базами данных",
]
from routers import admin, ai, integrations, schedules, subjects, teacher, tests
from schemas import Token, UserCreate, UserRead

# Учётная запись администратора по умолчанию (единственная)
DEFAULT_ADMIN_EMAIL = "batamir5@gmail.com"
DEFAULT_ADMIN_NAME = "Batyr-Bayan"
DEFAULT_ADMIN_PASSWORD = "Aadmin999"


def ensure_default_admin():
    """Создаёт администратора по умолчанию, если его ещё нет."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
        if existing:
            if existing.role != "admin":
                existing.role = "admin"
                existing.full_name = DEFAULT_ADMIN_NAME
                existing.password_hash = get_password_hash(DEFAULT_ADMIN_PASSWORD)
                existing.status = True
                db.commit()
            return
        admin_user = User(
            full_name=DEFAULT_ADMIN_NAME,
            email=DEFAULT_ADMIN_EMAIL,
            password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            role="admin",
            status=True,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()


def ensure_default_subjects():
    """Создаёт предметы по умолчанию, если их ещё нет."""
    db = SessionLocal()
    try:
        for name in DEFAULT_SUBJECTS:
            if not db.query(Subject).filter(Subject.name == name).first():
                db.add(Subject(name=name, description=None))
        db.commit()
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_default_admin()
    ensure_default_subjects()
    ensure_default_tests()
    try:
        seed_demo_students()
    except SystemExit:
        pass
    except Exception as exc:
        print(f"[seed_demo] skipped: {exc}")
    yield


app = FastAPI(
    title="Система самоконтроля подготовки к экзаменам",
    description="Учебный проект по модулям 1–2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(subjects.router)
app.include_router(tests.router)
app.include_router(schedules.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(integrations.router)
app.include_router(ai.router)

app.mount("/app", StaticFiles(directory="static", html=True), name="app")


@app.post("/auth/register", response_model=UserRead, tags=["Auth"])
async def register(user_in: UserCreate, db: DBSession) -> UserRead:
    try:
        return await register_user(user_in, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/token", response_model=Token, tags=["Auth"])
async def login(
    db: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    return await login_for_access_token(form_data, db)


@app.get("/auth/me", response_model=UserRead, tags=["Auth"])
async def get_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@app.get("/", tags=["Health"])
async def root():
    return RedirectResponse(url="/app/", status_code=302)

