from collections import defaultdict
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import joinedload

from auth import DBSession, get_current_user
from models import Answer, Question, Subject, Test, TestResult, Topic, User
from schemas import (
    StudentInsightsRead,
    StudentProgressRead,
    StudentStudyPlanRead,
    SubjectProgressRead,
    TestAnswer,
    TestCreate,
    TestHistoryItemRead,
    TestRead,
    TopicStatRead,
    QuestionExplanationRead,
    UserRead,
    WrongQuestionLinkRead,
)
from services.analytics import (
    build_student_insights,
    build_student_study_plan,
    build_subject_resources,
    generate_recommendations_for_test,
    get_level_label,
)


router = APIRouter(prefix="/tests", tags=["Tests"])


def _topic_stats_from_results(results: list[TestResult]) -> list[TopicStatRead]:
    topic_mistakes: dict[tuple[int, str], int] = defaultdict(int)
    for result in results:
        if result.is_correct or not result.question or not result.question.topic:
            continue
        topic_key = (result.question.topic.id, result.question.topic.name)
        topic_mistakes[topic_key] += 1

    ordered = sorted(topic_mistakes.items(), key=lambda item: item[1], reverse=True)
    return [
        TopicStatRead(topic_id=topic_id, topic_name=topic_name, mistakes=mistakes)
        for (topic_id, topic_name), mistakes in ordered[:3]
    ]


def _history_item_from_test(test: Test) -> TestHistoryItemRead:
    results = list(test.results or [])
    correct_answers = sum(1 for result in results if result.is_correct)
    weak_topics = _topic_stats_from_results(results)
    wrong_questions: list[WrongQuestionLinkRead] = []
    for result in results:
        # Показываем вопросы, где ответ неверный (включая "не ответил" / selected_answer_id == None).
        if not result.question or result.is_correct:
            continue
        question_text = result.question.question_text or f"Вопрос {result.question_id}"
        topic_name = result.question.topic.name if result.question.topic else None
        wrong_questions.append(
            WrongQuestionLinkRead(
                test_id=test.id,
                question_id=result.question_id,
                question_text=question_text,
                topic_name=topic_name,
                help_url=f"/app/question-explanation.html?test_id={test.id}&question_id={result.question_id}",
            )
        )
    return TestHistoryItemRead(
        id=test.id,
        subject_id=test.subject_id,
        subject_name=test.subject.name if test.subject else f"Предмет {test.subject_id}",
        created_at=test.created_at,
        score=float(test.score or 0),
        test_type=test.test_type,
        total_questions=len(results),
        correct_answers=correct_answers,
        level=get_level_label(float(test.score or 0)),
        weak_topics=weak_topics,
        wrong_questions=wrong_questions,
    )


@router.post("/", response_model=TestRead)
def start_test(
    test_in: TestCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> TestRead:
    if test_in.test_type not in ("quick", "full"):
        raise HTTPException(status_code=400, detail="test_type должен быть quick или full")
    test = Test(
        user_id=current_user.id,
        subject_id=test_in.subject_id,
        test_type=test_in.test_type,
        created_at=datetime.utcnow(),
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return TestRead.model_validate(test)


@router.post("/{test_id}/submit", response_model=TestRead)
def submit_test(
    test_id: int,
    answers: List[TestAnswer],
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> TestRead:
    test = db.query(Test).filter(Test.id == test_id, Test.user_id == current_user.id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")

    db.query(TestResult).filter(TestResult.test_id == test.id).delete()

    for ans in answers:
        question = db.query(Question).filter(Question.id == ans.question_id).first()
        if not question:
            raise HTTPException(status_code=400, detail=f"Вопрос {ans.question_id} не найден")

        selected_answer = None
        is_correct = False

        if ans.selected_answer_id is not None:
            selected_answer = (
                db.query(Answer)
                .filter(Answer.id == ans.selected_answer_id, Answer.question_id == question.id)
                .first()
            )
            if not selected_answer:
                raise HTTPException(status_code=400, detail=f"Ответ {ans.selected_answer_id} не найден")
            is_correct = selected_answer.is_correct

        result = TestResult(
            test_id=test.id,
            question_id=question.id,
            selected_answer_id=selected_answer.id if selected_answer else None,
            answer_text=ans.answer_text,
            is_correct=is_correct,
        )
        db.add(result)

    db.commit()
    db.refresh(test)

    generate_recommendations_for_test(db, test, current_user)
    db.refresh(test)

    return TestRead.model_validate(test)


@router.get("/", response_model=List[TestRead])
def list_my_tests(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> List[TestRead]:
    tests = db.query(Test).filter(Test.user_id == current_user.id).order_by(Test.created_at.desc()).all()
    return [TestRead.model_validate(t) for t in tests]


@router.get("/profile", response_model=UserRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/history", response_model=List[TestHistoryItemRead])
def list_test_history(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> List[TestHistoryItemRead]:
    tests = (
        db.query(Test)
        .options(
            joinedload(Test.subject),
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
        )
        .filter(Test.user_id == current_user.id)
        .order_by(Test.created_at.desc())
        .all()
    )
    return [_history_item_from_test(test) for test in tests]


@router.get("/progress", response_model=StudentProgressRead)
def get_student_progress(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> StudentProgressRead:
    tests = (
        db.query(Test)
        .options(
            joinedload(Test.subject),
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
        )
        .filter(Test.user_id == current_user.id)
        .order_by(Test.created_at.desc())
        .all()
    )

    if not tests:
        return StudentProgressRead(
            total_tests=0,
            average_score=0,
            completed_subjects=0,
            latest_activity=None,
            strongest_subject=None,
            weakest_subject=None,
            subjects=[],
        )

    subject_groups: dict[int, list[Test]] = defaultdict(list)
    for test in tests:
        subject_groups[test.subject_id].append(test)

    # Все предметы в системе — чтобы показать полный профиль, включая непройденные
    all_subjects: list[Subject] = db.query(Subject).order_by(Subject.name).all()

    subject_progress: list[SubjectProgressRead] = []
    for subject in all_subjects:
        subject_tests = subject_groups.get(subject.id, [])
        if subject_tests:
            scores = [float(t.score or 0) for t in subject_tests]
            latest_test = max(subject_tests, key=lambda t: t.created_at)
            all_results: list[TestResult] = []
            for t in subject_tests:
                all_results.extend(t.results or [])
            subject_progress.append(
                SubjectProgressRead(
                    subject_id=subject.id,
                    subject_name=subject.name,
                    total_tests=len(subject_tests),
                    average_score=round(sum(scores) / len(scores), 2),
                    best_score=max(scores),
                    latest_score=float(latest_test.score or 0),
                    level=get_level_label(round(sum(scores) / len(scores), 2)),
                    weak_topics=_topic_stats_from_results(all_results),
                )
            )
        else:
            # Предмет есть в системе, но студент ещё не проходил по нему тест
            subject_progress.append(
                SubjectProgressRead(
                    subject_id=subject.id,
                    subject_name=subject.name,
                    total_tests=0,
                    average_score=0.0,
                    best_score=0.0,
                    latest_score=0.0,
                    level="не начат",
                    weak_topics=[],
                )
            )

    tested = [s for s in subject_progress if s.total_tests > 0]
    sorted_by_avg = sorted(tested, key=lambda item: item.average_score)
    overall_average = round(
        sum(float(test.score or 0) for test in tests) / len(tests),
        2,
    )

    # Сначала пройденные (по убыванию балла), потом непройденные
    subjects_sorted = (
        sorted(tested, key=lambda s: s.average_score, reverse=True) +
        [s for s in subject_progress if s.total_tests == 0]
    )

    return StudentProgressRead(
        total_tests=len(tests),
        average_score=overall_average,
        completed_subjects=len(tested),
        latest_activity=max(test.created_at for test in tests),
        strongest_subject=sorted_by_avg[-1].subject_name if sorted_by_avg else None,
        weakest_subject=sorted_by_avg[0].subject_name if sorted_by_avg else None,
        subjects=subjects_sorted,
    )


@router.get("/insights", response_model=StudentInsightsRead)
def get_student_insights(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> StudentInsightsRead:
    tests = (
        db.query(Test)
        .options(
            joinedload(Test.subject),
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
        )
        .filter(Test.user_id == current_user.id)
        .order_by(Test.created_at.desc())
        .all()
    )
    return build_student_insights(tests)


@router.get("/study-plan", response_model=StudentStudyPlanRead)
def get_student_study_plan(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> StudentStudyPlanRead:
    tests = (
        db.query(Test)
        .options(
            joinedload(Test.subject),
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
        )
        .filter(Test.user_id == current_user.id)
        .order_by(Test.created_at.desc())
        .all()
    )
    insights = build_student_insights(tests)
    return build_student_study_plan(insights)


@router.get("/{test_id}/questions/{question_id}/explanation", response_model=QuestionExplanationRead)
def get_question_explanation(
    test_id: int,
    question_id: int,
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> QuestionExplanationRead:
    test = (
        db.query(Test)
        .options(joinedload(Test.subject))
        .filter(Test.id == test_id, Test.user_id == current_user.id)
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")

    result = (
        db.query(TestResult)
        .filter(TestResult.test_id == test_id, TestResult.question_id == question_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Результат по вопросу не найден")

    question = (
        db.query(Question)
        .options(joinedload(Question.answers), joinedload(Question.topic).joinedload(Topic.subject))
        .filter(Question.id == question_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    correct_answers = [a.answer_text for a in (question.answers or []) if a.is_correct]
    selected_answer_text = None
    if result.selected_answer_id is not None:
        selected_answer = next((a for a in question.answers if a.id == result.selected_answer_id), None)
        selected_answer_text = selected_answer.answer_text if selected_answer else None

    status = "unanswered" if result.selected_answer_id is None else ("incorrect" if not result.is_correct else "unknown")

    resources = build_subject_resources(test.subject.name if test.subject else None)

    return QuestionExplanationRead(
        test_id=test_id,
        question_id=question_id,
        subject_name=test.subject.name if test.subject else None,
        topic_name=question.topic.name if question.topic else None,
        question_text=question.question_text,
        status=status,
        selected_answer_text=selected_answer_text,
        correct_answers=correct_answers,
        resources=resources,
    )

