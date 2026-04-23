import random
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from auth import DBSession, require_role
from database import get_db
from models import Answer, Question, Subject, Topic, QuestionTypeEnum
from schemas import (
    AnswerRead,
    QuestionCreate,
    QuestionRead,
    SubjectCreate,
    SubjectRead,
    TopicCreate,
    TopicRead,
)


router = APIRouter(prefix="/subjects", tags=["Subjects & Questions"])

TEST_QUESTION_LIMITS = {
    "quick": 15,
    "full": 30,
}


def _normalize_answers_for_test(question: Question) -> QuestionRead | None:
    unique_answers: list[AnswerRead] = []
    seen_texts: set[str] = set()

    for answer in question.answers:
        key = answer.answer_text.strip().casefold()
        if not key or key in seen_texts:
            continue
        seen_texts.add(key)
        unique_answers.append(AnswerRead.model_validate(answer))

    correct_answers = [answer for answer in unique_answers if answer.is_correct]
    wrong_answers = [answer for answer in unique_answers if not answer.is_correct]

    if not correct_answers or len(wrong_answers) < 3:
        return None

    selected_answers = [correct_answers[0], *wrong_answers[:3]]
    random.shuffle(selected_answers)

    question_read = QuestionRead.model_validate(question)
    question_read.answers = selected_answers
    return question_read


def _question_text_key(question_text: str | None) -> str:
    return (question_text or "").strip().casefold()


@router.post("/", response_model=SubjectRead, dependencies=[Depends(require_role("teacher", "admin"))])
def create_subject(subject_in: SubjectCreate, db: DBSession) -> SubjectRead:
    name = (subject_in.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Название предмета не может быть пустым")
    existing = db.query(Subject).filter(Subject.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Предмет с таким названием уже существует")
    subject = Subject(name=name, description=subject_in.description)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return SubjectRead.model_validate(subject)


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("admin"))],
)
def delete_subject(subject_id: int, db: DBSession) -> None:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    db.delete(subject)
    db.commit()


@router.get("/", response_model=List[SubjectRead])
def list_subjects(db: DBSession) -> List[SubjectRead]:
    subjects = db.query(Subject).all()
    return [SubjectRead.model_validate(s) for s in subjects]


@router.post("/topics", response_model=TopicRead, dependencies=[Depends(require_role("teacher", "admin"))])
def create_topic(topic_in: TopicCreate, db: DBSession) -> TopicRead:
    subject = db.query(Subject).filter(Subject.id == topic_in.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    topic = Topic(
        name=topic_in.name,
        difficulty_level=topic_in.difficulty_level or 1,
        subject_id=topic_in.subject_id,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return TopicRead.model_validate(topic)


@router.get("/{subject_id}/topics", response_model=List[TopicRead])
def list_topics(subject_id: int, db: DBSession) -> List[TopicRead]:
    topics = db.query(Topic).filter(Topic.subject_id == subject_id).all()
    return [TopicRead.model_validate(t) for t in topics]


@router.post("/questions", response_model=QuestionRead, dependencies=[Depends(require_role("teacher", "admin"))])
def create_question(question_in: QuestionCreate, db: DBSession) -> QuestionRead:
    topic = db.query(Topic).filter(Topic.id == question_in.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Тема не найдена")

    if question_in.question_type not in (
        QuestionTypeEnum.SINGLE,
        QuestionTypeEnum.MULTIPLE,
        QuestionTypeEnum.OPEN,
    ):
        raise HTTPException(status_code=400, detail="Некорректный тип вопроса")

    question = Question(
        topic_id=question_in.topic_id,
        question_text=question_in.question_text,
        question_type=question_in.question_type,
    )
    db.add(question)
    db.flush()

    for ans in question_in.answers:
        answer = Answer(
            question_id=question.id,
            answer_text=ans.answer_text,
            is_correct=ans.is_correct,
        )
        db.add(answer)

    db.commit()
    db.refresh(question)
    return QuestionRead.model_validate(question)


@router.get("/topics/{topic_id}/questions", response_model=List[QuestionRead])
def list_questions(topic_id: int, db: DBSession) -> List[QuestionRead]:
    questions = db.query(Question).filter(Question.topic_id == topic_id).all()
    return [QuestionRead.model_validate(q) for q in questions]


@router.get("/{subject_id}/questions", response_model=List[QuestionRead])
def list_questions_for_test(
    subject_id: int,
    db: DBSession,
    test_type: str = Query("quick", description="quick — лёгкий, full — полный"),
) -> List[QuestionRead]:
    """Вопросы для теста: quick — лёгкие темы (difficulty 1-2), full — все."""
    if test_type not in TEST_QUESTION_LIMITS:
        raise HTTPException(status_code=400, detail="test_type должен быть quick или full")

    topics = db.query(Topic).filter(Topic.subject_id == subject_id)
    if test_type == "quick":
        topics = topics.filter(Topic.difficulty_level <= 2)
    topic_ids = [t.id for t in topics.all()]
    if not topic_ids:
        return []
    questions = (
        db.query(Question)
        .options(joinedload(Question.answers))
        .filter(Question.topic_id.in_(topic_ids))
        .filter(~Question.question_text.like("%тренировочный вопрос%"))
        .order_by(Question.topic_id, Question.id)
        .all()
    )
    random.shuffle(questions)
    result: list[QuestionRead] = []
    seen_question_texts: set[str] = set()
    for question in questions:
        question_key = _question_text_key(question.question_text)
        if not question_key or question_key in seen_question_texts:
            continue
        normalized_question = _normalize_answers_for_test(question)
        if not normalized_question:
            continue
        seen_question_texts.add(question_key)
        result.append(normalized_question)
        if len(result) >= TEST_QUESTION_LIMITS[test_type]:
            break
    return result

