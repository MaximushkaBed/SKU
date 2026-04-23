"""
Демо-данные для презентации преподавателю.

Создаёт 5 студентов с разными профилями успеваемости:
  - Айгерим  — отличник (88–95%), активно тестируется
  - Данияр   — хорошист (65–80%), умеренная частота
  - Карина   — средний (50–65%), неравномерные результаты
  - Нурлан   — слабый (35–50%), редко тестируется
  - Алия     — низкий (15–35%), только начинает

У каждого студента — история тестов за последние 45–60 дней по нескольким предметам.
Тесты содержат реальные TestResult с правильными/неправильными ответами.

Запуск:
  python seed_demo.py
"""

import random
import sys
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from auth import get_password_hash
from database import SessionLocal
from models import Answer, Notification, Question, Recommendation, Schedule, Subject, Test, TestResult, Topic, User


# ─── Профили студентов ───────────────────────────────────────────────────────

DEMO_STUDENTS = [
    {
        "full_name": "Айгерим Сейткали",
        "email": "aigerim.demo@student.test",
        "password": "Demo1234",
        # accuracy per subject (0-1), None = пропустить предмет
        "subject_accuracy": {
            1: 0.92,   # Казахский язык
            2: 0.88,   # Английский язык
            4: 0.85,   # Высшая математика
            5: 0.91,   # История Казахстана
            6: 0.87,   # Политология
        },
        "tests_per_subject": 6,
        "days_spread": 50,
    },
    {
        "full_name": "Данияр Ахметов",
        "email": "daniyar.demo@student.test",
        "password": "Demo1234",
        "subject_accuracy": {
            1: 0.72,   # Казахский язык
            3: 0.68,   # Русский язык
            4: 0.75,   # Высшая математика
            8: 0.71,   # Анализ данных
        },
        "tests_per_subject": 5,
        "days_spread": 40,
    },
    {
        "full_name": "Карина Петрова",
        "email": "karina.demo@student.test",
        "password": "Demo1234",
        "subject_accuracy": {
            2: 0.62,   # Английский язык
            3: 0.55,   # Русский язык
            9: 0.58,   # Web-программирование
            10: 0.51,  # Языки и технологии
        },
        "tests_per_subject": 4,
        "days_spread": 35,
    },
    {
        "full_name": "Нурлан Касымов",
        "email": "nurlan.demo@student.test",
        "password": "Demo1234",
        "subject_accuracy": {
            1: 0.42,   # Казахский язык
            5: 0.38,   # История Казахстана
            7: 0.45,   # Социология
        },
        "tests_per_subject": 3,
        "days_spread": 25,
    },
    {
        "full_name": "Алия Жумабекова",
        "email": "aliya.demo@student.test",
        "password": "Demo1234",
        "subject_accuracy": {
            3: 0.28,   # Русский язык
            5: 0.22,   # История Казахстана
        },
        "tests_per_subject": 2,
        "days_spread": 15,
    },
]


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def get_questions_by_subject(db: Session, subject_id: int) -> list[Question]:
    topics = db.query(Topic).filter(Topic.subject_id == subject_id).all()
    topic_ids = [t.id for t in topics]
    return (
        db.query(Question)
        .options(joinedload(Question.answers))
        .filter(Question.topic_id.in_(topic_ids))
        .all()
    )


def simulate_test(
    db: Session,
    user: User,
    subject_id: int,
    questions: list[Question],
    accuracy: float,
    created_at: datetime,
    test_type: str = "quick",
    rng: random.Random = None,
) -> Test:
    """Создаёт тест с результатами, имитируя заданную точность ответов."""
    if rng is None:
        rng = random.Random()

    # Берём случайную выборку вопросов (10 для quick, 15 для full)
    n_questions = 10 if test_type == "quick" else 15
    sample = rng.sample(questions, min(n_questions, len(questions)))

    test = Test(
        user_id=user.id,
        subject_id=subject_id,
        test_type=test_type,
        score=0.0,
        created_at=created_at,
    )
    db.add(test)
    db.flush()  # получаем test.id

    correct_count = 0
    for question in sample:
        correct_answers = [a for a in question.answers if a.is_correct]
        wrong_answers = [a for a in question.answers if not a.is_correct]

        # Случайно решаем: правильно ли ответил студент
        # Добавляем немного шума: ±0.15 от базовой точности
        noise = rng.uniform(-0.12, 0.12)
        is_correct = rng.random() < max(0.05, min(0.98, accuracy + noise))

        if is_correct and correct_answers:
            selected = rng.choice(correct_answers)
        elif wrong_answers:
            selected = rng.choice(wrong_answers)
        elif correct_answers:
            selected = rng.choice(correct_answers)
            is_correct = True
        else:
            selected = None
            is_correct = False

        result = TestResult(
            test_id=test.id,
            question_id=question.id,
            selected_answer_id=selected.id if selected else None,
            is_correct=is_correct,
        )
        db.add(result)
        if is_correct:
            correct_count += 1

    # Вычисляем балл
    score = round(100.0 * correct_count / len(sample), 2) if sample else 0.0
    test.score = score

    # Рекомендация
    if score < 60:
        rec_text = (
            f"Балл {score}% — низкий уровень. Рекомендуется интенсивный план: "
            "ежедневные короткие сессии 30–40 минут, повторение базовых тем, "
            "использование метода интервального повторения (Эббингауз)."
        )
    elif score < 85:
        rec_text = (
            f"Балл {score}% — средний уровень. Целенаправленная доработка пробелов: "
            "уделите больше внимания сложным темам, чередуйте повторение и практику, "
            "применяйте технику Помодоро для поддержания концентрации."
        )
    else:
        rec_text = (
            f"Балл {score}% — высокий уровень. Поддерживающий режим: "
            "периодическое повторение ключевых тем, контрольные тесты ближе к экзамену."
        )

    recommendation = Recommendation(
        user_id=user.id,
        test_id=test.id,
        recommendation_text=rec_text,
    )
    db.add(recommendation)

    return test


# ─── Основной скрипт ─────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    rng = random.Random(2024)  # фиксированный seed для воспроизводимости

    try:
        now = datetime.utcnow()
        created_count = 0
        skipped_count = 0

        for profile in DEMO_STUDENTS:
            # Проверяем: уже создан?
            existing = db.query(User).filter(User.email == profile["email"]).first()
            if existing:
                print(f"  SKIP  {profile['full_name']} — уже существует")
                skipped_count += 1
                continue

            # Создаём студента
            user = User(
                full_name=profile["full_name"],
                email=profile["email"],
                password_hash=get_password_hash(profile["password"]),
                role="student",
                status=True,
            )
            db.add(user)
            db.flush()

            # Создаём тесты по каждому предмету
            tests_per_subj = profile["tests_per_subject"]
            days_spread = profile["days_spread"]

            for subject_id, accuracy in profile["subject_accuracy"].items():
                questions = get_questions_by_subject(db, subject_id)
                if not questions:
                    continue

                for i in range(tests_per_subj):
                    # Равномерно распределяем тесты по времени (от days_spread дней назад до сегодня)
                    days_ago = days_spread - (i * days_spread / max(1, tests_per_subj - 1))
                    jitter = rng.uniform(-2, 2)
                    created_at = now - timedelta(days=max(0.5, days_ago + jitter))

                    # Чередуем quick/full
                    test_type = "quick" if i % 3 != 2 else "full"

                    simulate_test(
                        db=db,
                        user=user,
                        subject_id=subject_id,
                        questions=questions,
                        accuracy=accuracy,
                        created_at=created_at,
                        test_type=test_type,
                        rng=rng,
                    )

            # Уведомление приветствия
            notif = Notification(
                user_id=user.id,
                message=f"Добро пожаловать, {user.full_name.split()[0]}! Ваш профиль создан. Начните с первого теста.",
                type="info",
                is_read=False,
            )
            db.add(notif)

            db.commit()
            print(f"  OK    {profile['full_name']} ({profile['email']}) — тестов: {tests_per_subj * len(profile['subject_accuracy'])}")
            created_count += 1

        print(f"\nГотово: создано {created_count}, пропущено {skipped_count}.")
        print("Логин: <email>  Пароль: Demo1234")

    except Exception as e:
        db.rollback()
        print(f"\nОШИБКА: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
