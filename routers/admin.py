from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models import Question, User
from schemas import QuestionRead, UserRead


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=List[UserRead], dependencies=[Depends(require_role("admin"))])
def list_users(db: Session = Depends(get_db)) -> List[UserRead]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserRead.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserRead, dependencies=[Depends(require_role("admin"))])
def update_user(
    user_id: int,
    role: Optional[str] = Query(default=None, description="Новая роль: student/teacher/admin"),
    active: Optional[bool] = Query(default=None, description="Статус учетной записи"),
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if role is not None:
        user.role = role
    if active is not None:
        user.status = active
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/logs", dependencies=[Depends(require_role("admin"))])
def get_system_logs() -> dict:
    return {
        "note": "Учебная заглушка. В реальном развёртывании здесь возвращаются системные логи/журналы.",
    }


@router.patch(
    "/questions/{question_id}",
    response_model=QuestionRead,
    dependencies=[Depends(require_role("admin"))],
)
def edit_question(
    question_id: int,
    text: Optional[str] = Query(default=None, description="Новый текст вопроса"),
    db: Session = Depends(get_db),
) -> QuestionRead:
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    if text is not None:
        question.question_text = text
    db.commit()
    db.refresh(question)
    return QuestionRead.model_validate(question)


@router.delete(
    "/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
)
def delete_question(question_id: int, db: Session = Depends(get_db)) -> None:
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    db.delete(question)
    db.commit()

