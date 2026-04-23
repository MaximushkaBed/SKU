from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload

from auth import DBSession, require_role
from models import Question, Schedule, Test, TestResult, Topic, User
from services.analytics import get_level_label


router = APIRouter(prefix="/teacher", tags=["Teacher"])


@router.get(
    "/subjects/{subject_id}/report",
    dependencies=[Depends(require_role("teacher", "admin"))],
)
def subject_group_report(subject_id: int, db: DBSession) -> dict:
    subject_tests = (
        db.query(Test)
        .options(
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
            joinedload(Test.user),
        )
        .filter(Test.subject_id == subject_id)
        .all()
    )
    student_buckets: dict[int, dict] = {}
    for test in subject_tests:
        if not test.user:
            continue
        bucket = student_buckets.setdefault(
            test.user.id,
            {
                "user_id": test.user.id,
                "full_name": test.user.full_name,
                "scores": [],
            },
        )
        bucket["scores"].append(float(test.score or 0))

    score_distribution = {"низкий": 0, "средний": 0, "высокий": 0}
    topic_counter: dict[tuple[int, str], int] = {}
    for test in subject_tests:
        level = get_level_label(float(test.score or 0))
        score_distribution[level] += 1
        for result in test.results or []:
            if result.is_correct or not result.question or not result.question.topic:
                continue
            key = (result.question.topic.id, result.question.topic.name)
            topic_counter[key] = topic_counter.get(key, 0) + 1

    weak_topics = [
        {"topic_id": topic_id, "topic_name": topic_name, "mistakes": mistakes}
        for (topic_id, topic_name), mistakes in sorted(topic_counter.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    avg_score = (
        round(sum(float(test.score or 0) for test in subject_tests) / len(subject_tests), 2)
        if subject_tests
        else None
    )

    return {
        "subject_id": subject_id,
        "summary": {
            "students_count": len(student_buckets),
            "tests_count": len(subject_tests),
            "average_score": avg_score,
            "score_distribution": score_distribution,
            "weak_topics": weak_topics,
        },
        "students": sorted(
            [
                {
                    "user_id": bucket["user_id"],
                    "full_name": bucket["full_name"],
                    "tests_count": len(bucket["scores"]),
                    "avg_score": round(sum(bucket["scores"]) / len(bucket["scores"]), 2) if bucket["scores"] else None,
                    "level": get_level_label(round(sum(bucket["scores"]) / len(bucket["scores"]), 2))
                    if bucket["scores"]
                    else "нет данных",
                }
                for bucket in student_buckets.values()
            ],
            key=lambda item: (item["avg_score"] is None, -(item["avg_score"] or 0)),
        ),
    }


@router.post(
    "/assignments",
    dependencies=[Depends(require_role("teacher", "admin"))],
)
def create_assignments(
    topic_id: int,
    user_ids: List[int],
    db: DBSession,
) -> dict:
    now = datetime.utcnow()
    for uid in user_ids:
        schedule = Schedule(
            user_id=uid,
            topic_id=topic_id,
            scheduled_date=now,
            status="planned",
        )
        db.add(schedule)
    db.commit()
    return {"message": "Задания назначены", "topic_id": topic_id, "users": user_ids}


@router.post(
    "/external-results",
    dependencies=[Depends(require_role("teacher", "admin"))],
)
def add_external_result(
    user_id: int,
    subject_id: int,
    score: float,
    db: DBSession,
    test_type: str = "full",
) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Студент не найден")
    if test_type not in ("quick", "full"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="test_type должен быть quick или full")
    test = Test(
        user_id=user_id,
        subject_id=subject_id,
        score=score,
        test_type=test_type,
        created_at=datetime.utcnow(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return {"message": "Внешний результат добавлен", "test_id": test.id}

