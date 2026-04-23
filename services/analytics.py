from collections import Counter
from datetime import datetime, timedelta
from typing import Iterable
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from models import Recommendation, Schedule, Topic, Test, TestResult, User
from schemas import (
    ResourceLinkRead,
    StudentInsightsRead,
    StudentStudyPlanRead,
    StudyActionRead,
    StudyPlanItemRead,
    TopicStatRead,
)


STUDY_METHOD_TIPS = [
    ResourceLinkRead(
        title="Метод Помодоро — таймер 25/5",
        url="https://pomofocus.io/",
        resource_type="tool",
        description="Работайте 25 минут, затем 5 минут перерыв. Повышает концентрацию и снижает усталость.",
    ),
    ResourceLinkRead(
        title="Интервальное повторение (Anki)",
        url="https://apps.ankiweb.net/",
        resource_type="tool",
        description="Система карточек на основе кривой забывания Эббингауза. Повторяйте материал в нужный момент.",
    ),
    ResourceLinkRead(
        title="Khan Academy — бесплатные курсы",
        url="https://ru.khanacademy.org/",
        resource_type="course",
        description="Полные видеокурсы по математике, языкам, истории и другим предметам.",
    ),
]

SUBJECT_RESOURCE_MAP = {
    "Высшая математика": [
        ("Khan Academy: Math", "https://www.khanacademy.org/math", "course", "Базовый и продвинутый материал по математике."),
        ("Paul's Online Math Notes", "https://tutorial.math.lamar.edu/", "article", "Подробные разборы тем по высшей математике."),
    ],
    "Анализ данных": [
        ("Kaggle Learn", "https://www.kaggle.com/learn", "course", "Практические микро-курсы по анализу данных."),
        ("StatQuest", "https://www.youtube.com/@statquest", "video", "Понятные видео по статистике и ML."),
    ],
    "Web-программирование": [
        ("MDN Web Docs", "https://developer.mozilla.org/ru/", "documentation", "Лучшая документация по HTML, CSS, JavaScript."),
        ("freeCodeCamp", "https://www.freecodecamp.org/learn/", "course", "Бесплатные курсы по веб-разработке."),
    ],
    "Системы управления базами данных": [
        ("SQLBolt", "https://sqlbolt.com/", "course", "Интерактивное изучение SQL."),
        ("PostgreSQL Tutorial", "https://www.postgresqltutorial.com/", "article", "Пошаговые уроки по SQL и БД."),
    ],
    "Языки и технологии программирования": [
        ("freeCodeCamp: Algorithms", "https://www.freecodecamp.org/learn/", "course", "Практика по алгоритмам и программированию."),
        ("GeeksforGeeks", "https://www.geeksforgeeks.org/", "article", "Справочник по структурам данных и алгоритмам."),
    ],
    "Английский язык": [
        ("British Council", "https://learnenglish.britishcouncil.org/", "course", "Материалы и задания по английскому языку."),
        ("BBC Learning English", "https://www.bbc.co.uk/learningenglish", "video", "Короткие уроки и объяснения тем."),
    ],
}


def _calculate_score(results: Iterable[TestResult]) -> float:
    total = 0
    correct = 0
    for r in results:
        total += 1
        if r.is_correct:
            correct += 1
    if total == 0:
        return 0.0
    return round(100.0 * correct / total, 2)


def get_level_label(score: float) -> str:
    if score < 60:
        return "низкий"
    if score < 85:
        return "средний"
    return "высокий"


def get_trend_label(scores: list[float]) -> str:
    if len(scores) < 3:
        return "недостаточно данных"

    recent = scores[:3]
    previous = scores[3:6]
    if not previous:
        return "стабильный"

    recent_avg = sum(recent) / len(recent)
    previous_avg = sum(previous) / len(previous)
    delta = recent_avg - previous_avg

    if delta >= 5:
        return "улучшается"
    if delta <= -5:
        return "снижается"
    return "стабильный"


def _build_resource_links(focus_subject: str | None, priority_topics: list[TopicStatRead]) -> list[ResourceLinkRead]:
    resources: list[ResourceLinkRead] = []
    seen_urls: set[str] = set()

    if focus_subject and focus_subject in SUBJECT_RESOURCE_MAP:
        for title, url, resource_type, description in SUBJECT_RESOURCE_MAP[focus_subject]:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            resources.append(
                ResourceLinkRead(
                    title=title,
                    url=url,
                    resource_type=resource_type,
                    description=description,
                )
            )

    if focus_subject:
        query = quote_plus(f"{focus_subject} обучение курс")
        google_url = f"https://www.google.com/search?q={query}"
        youtube_url = f"https://www.youtube.com/results?search_query={query}"
        for title, url, resource_type, description in [
            ("Подборка статей по предмету", google_url, "search", f"Быстрый поиск статей и разборов по предмету «{focus_subject}»."),
            ("Видео по предмету", youtube_url, "video", f"Видео-уроки и объяснения по предмету «{focus_subject}»."),
        ]:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            resources.append(
                ResourceLinkRead(
                    title=title,
                    url=url,
                    resource_type=resource_type,
                    description=description,
                )
            )

    for topic in priority_topics[:3]:
        google_query = quote_plus(topic.topic_name)
        youtube_query = quote_plus(topic.topic_name + " разбор")
        topic_links = [
            (
                f"Статьи по теме: {topic.topic_name}",
                f"https://www.google.com/search?q={google_query}",
                "search",
                f"Подборка материалов и объяснений по теме «{topic.topic_name}».",
            ),
            (
                f"Видео-разбор: {topic.topic_name}",
                f"https://www.youtube.com/results?search_query={youtube_query}",
                "video",
                f"Видео-объяснения и решения задач по теме «{topic.topic_name}».",
            ),
        ]
        for title, url, resource_type, description in topic_links:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            resources.append(
                ResourceLinkRead(
                    title=title,
                    url=url,
                    resource_type=resource_type,
                    description=description,
                )
            )

    return resources[:8]


def build_subject_resources(subject_name: str | None) -> list[ResourceLinkRead]:
    """Дает прямые ссылки по предмету (без поиска)."""
    if not subject_name:
        return []
    if subject_name not in SUBJECT_RESOURCE_MAP:
        return []

    resources: list[ResourceLinkRead] = []
    for title, url, resource_type, description in SUBJECT_RESOURCE_MAP[subject_name][:6]:
        resources.append(
            ResourceLinkRead(
                title=title,
                url=url,
                resource_type=resource_type,
                description=description,
            )
        )
    return resources


def build_student_insights(tests: list[Test]) -> StudentInsightsRead:
    if not tests:
        return StudentInsightsRead(
            current_level="начальный",
            average_score=0,
            trend="недостаточно данных",
            focus_subject=None,
            strongest_subject=None,
            recommended_test_subject=None,
            recommended_test_type="quick",
            motivation_message="Начните с быстрого теста по любому предмету, чтобы система построила персональный план.",
            priority_topics=[],
            action_plan=[
                StudyActionRead(
                    title="Пройти первый быстрый тест",
                    description="Выберите предмет и завершите хотя бы один быстрый тест для первичной диагностики.",
                    priority="high",
                ),
            ],
            resources=[
                ResourceLinkRead(
                    title="Подборка вводных материалов",
                    url="https://www.google.com/search?q=%D0%BA%D0%B0%D0%BA+%D0%BD%D0%B0%D1%87%D0%B0%D1%82%D1%8C+%D0%BF%D0%BE%D0%B4%D0%B3%D0%BE%D1%82%D0%BE%D0%B2%D0%BA%D1%83+%D0%BA+%D1%8D%D0%BA%D0%B7%D0%B0%D0%BC%D0%B5%D0%BD%D1%83",
                    resource_type="search",
                    description="Быстрый старт: общие материалы по планированию подготовки к экзаменам.",
                ),
            ],
        )

    ordered_tests = sorted(tests, key=lambda test: test.created_at, reverse=True)
    scores = [float(test.score or 0) for test in ordered_tests]
    average_score = round(sum(scores) / len(scores), 2)
    current_level = get_level_label(average_score)
    trend = get_trend_label(scores)

    subject_scores: dict[str, list[float]] = {}
    topic_counter: Counter[tuple[int, str]] = Counter()

    for test in ordered_tests:
        subject_name = test.subject.name if test.subject else f"Предмет {test.subject_id}"
        subject_scores.setdefault(subject_name, []).append(float(test.score or 0))
        for result in test.results or []:
            if result.is_correct or not result.question or not result.question.topic:
                continue
            topic_counter[(result.question.topic.id, result.question.topic.name)] += 1

    subject_averages = {
        subject_name: round(sum(values) / len(values), 2)
        for subject_name, values in subject_scores.items()
    }
    sorted_subjects = sorted(subject_averages.items(), key=lambda item: item[1])
    focus_subject = sorted_subjects[0][0] if sorted_subjects else None
    focus_subject_score = sorted_subjects[0][1] if sorted_subjects else 0
    strongest_subject = sorted_subjects[-1][0] if sorted_subjects else None

    recommended_test_type = "quick" if focus_subject_score < 70 else "full"
    priority_topics = [
        TopicStatRead(topic_id=topic_id, topic_name=topic_name, mistakes=mistakes)
        for (topic_id, topic_name), mistakes in sorted(topic_counter.items(), key=lambda item: item[1], reverse=True)[:4]
    ]

    action_plan: list[StudyActionRead] = []
    if focus_subject:
        action_plan.append(
            StudyActionRead(
                title=f"Сфокусироваться на предмете: {focus_subject}",
                description=f"Это предмет с самым низким средним баллом ({focus_subject_score}%). С него лучше начать следующий цикл подготовки.",
                priority="high",
            )
        )

    if priority_topics:
        action_plan.append(
            StudyActionRead(
                title="Повторить слабые темы",
                description="В первую очередь повторите: " + ", ".join(topic.topic_name for topic in priority_topics[:3]) + ".",
                priority="high",
            )
        )

    action_plan.append(
        StudyActionRead(
            title="Следующий рекомендуемый тест",
            description=(
                f"Пройдите {recommended_test_type} тест"
                + (f" по предмету «{focus_subject}»." if focus_subject else ".")
            ),
            priority="medium",
        )
    )

    if trend == "снижается":
        action_plan.append(
            StudyActionRead(
                title="Интервальное повторение слабых тем",
                description=(
                    "Последние результаты стали хуже. Используйте метод Эббингауза: "
                    "повторяйте слабые темы через 1 → 3 → 7 → 14 дней для закрепления в долгосрочной памяти."
                ),
                priority="high",
            )
        )
        action_plan.append(
            StudyActionRead(
                title="Сессии по технике Помодоро",
                description="Разбейте подготовку на блоки 25 минут с 5-минутными перерывами. Не более 4 блоков подряд.",
                priority="medium",
            )
        )
    elif trend == "улучшается":
        action_plan.append(
            StudyActionRead(
                title="Закрепить положительную динамику",
                description="Результаты улучшаются. Переходите к более сложным тестам по слабым предметам и составьте интеллект-карту ключевых тем.",
                priority="medium",
            )
        )
    else:
        action_plan.append(
            StudyActionRead(
                title="Групповое повторение и самопроверка",
                description=(
                    "Прогресс ровный. Попробуйте объяснить тему другому студенту (метод Фейнмана) "
                    "или составьте интеллект-карту — это укрепляет долгосрочную память."
                ),
                priority="medium",
            )
        )

    # Рекомендация на основе модели Эббингауза
    try:
        from services.intelligence import compute_subject_retention
        retention_map = compute_subject_retention(ordered_tests)
        risky = [(subj, d) for subj, d in retention_map.items() if d["needs_review"]]
        if risky:
            risky_names = ", ".join(f"«{s}» ({round(d['retention']*100)}% удержания)" for s, d in risky[:3])
            action_plan.append(
                StudyActionRead(
                    title="⚠ Повторить сейчас — риск забывания (Эббингауз)",
                    description=(
                        f"По модели Эббингауза уровень удержания ниже 60% для предметов: {risky_names}. "
                        "Рекомендуется немедленное повторение для предотвращения потери знаний."
                    ),
                    priority="high",
                )
            )
    except Exception:
        pass

    motivation_message = (
        f"Ваш текущий уровень подготовки — {current_level}. "
        + (
            f"Наибольшее внимание сейчас стоит уделить предмету «{focus_subject}». "
            if focus_subject
            else ""
        )
        + (
            "Динамика положительная, можно постепенно увеличивать сложность."
            if trend == "улучшается"
            else "Сделайте упор на интервальное повторение и точечную отработку ошибок."
            if trend == "снижается"
            else "Продолжайте системную подготовку и закрепляйте слабые темы."
        )
    )
    resources = _build_resource_links(focus_subject, priority_topics)
    # Добавляем инструменты подготовки в начало списка ресурсов
    resources = STUDY_METHOD_TIPS[:2] + resources

    return StudentInsightsRead(
        current_level=current_level,
        average_score=average_score,
        trend=trend,
        focus_subject=focus_subject,
        strongest_subject=strongest_subject,
        recommended_test_subject=focus_subject,
        recommended_test_type=recommended_test_type,
        motivation_message=motivation_message,
        priority_topics=priority_topics,
        action_plan=action_plan,
        resources=resources,
    )


def build_student_study_plan(insights: StudentInsightsRead) -> StudentStudyPlanRead:
    generated_at = datetime.utcnow()
    base_subject = insights.focus_subject or insights.recommended_test_subject or insights.strongest_subject
    # Берём до 2 слабейших тем — на каждую выделяем день теории + день практики
    # 1 диагностика + 2*N тем + 1 тест + 1 разбор = при N=2 ровно 7 дней
    weak_topics = insights.priority_topics[:2]

    items: list[StudyPlanItemRead] = []
    day_num = 1

    def add(title: str, item_type: str, priority: str, minutes: int, topic: str | None = None):
        nonlocal day_num
        items.append(StudyPlanItemRead(
            day_label=f"День {day_num}",
            title=title,
            focus_subject=base_subject,
            topic_name=topic,
            duration_minutes=minutes,
            item_type=item_type,
            priority=priority,
        ))
        day_num += 1

    # День 1: диагностика
    diag_topics = " + ".join(t.topic_name for t in weak_topics[:2]) if weak_topics else None
    add("Диагностика — разбор допущенных ошибок", "review", "high", 40, diag_topics)

    if weak_topics:
        # Для каждой слабой темы: день теории + день практики
        for topic in weak_topics:
            add(f"Изучить тему: {topic.topic_name}", "theory", "high", 45, topic.topic_name)
            add(f"Практика: {topic.topic_name}", "practice", "medium", 35, topic.topic_name)

        # Контрольный тест по всем слабым темам
        all_topics = ", ".join(t.topic_name for t in weak_topics)
        add("Контрольный тест по слабым темам", "test", "high", 50, all_topics)
    else:
        # Нет данных по темам — универсальный план
        add("Теория по основному предмету", "theory", "high", 45)
        add("Практика и мини-тест", "practice", "medium", 35)
        add("Контрольный тест", "test", "high", 50)

    # Последний день: итоговый разбор
    add("Итоговый разбор и план на следующую неделю", "reflection", "medium", 25)

    if weak_topics:
        topic_str = ", ".join(f"«{t.topic_name}»" for t in weak_topics)
        overview = (
            f"План на {len(items)} дней. "
            + (f"Предмет: {base_subject}. " if base_subject else "")
            + f"Слабые темы для проработки: {topic_str}. "
            + "Каждая тема получает день теории и день практики, затем контрольный тест."
        )
    else:
        overview = (
            f"План на {len(items)} дней. "
            + (f"Фокус — предмет «{base_subject}». " if base_subject else "")
            + "Пройдите больше тестов для составления детального плана по конкретным темам."
        )

    return StudentStudyPlanRead(
        generated_at=generated_at,
        horizon_days=len(items),
        overview=overview,
        items=items,
    )


def generate_recommendations_for_test(db: Session, test: Test, user: User) -> None:
    score = _calculate_score(test.results)
    test.score = score

    level = get_level_label(score)

    topic_counter: Counter[int] = Counter()
    for r in test.results:
        if not r.is_correct:
            topic_counter[r.question.topic_id] += 1

    weak_topics: list[str] = []
    if topic_counter:
        sorted_topics = sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)
        for topic_id, _ in sorted_topics[:3]:
            weak_topics.append(r.question.topic.name if (r := next(
                (res for res in test.results if res.question.topic_id == topic_id), None
            )) else f"Тема {topic_id}")

    weak_part = (
        "Слабо усвоенные темы: " + ", ".join(weak_topics) + ". "
        if weak_topics
        else "Слабо усвоенные темы по результатам теста не выявлены. "
    )

    if score < 60:
        strategy = (
            "Рекомендуется интенсивный план подготовки: ежедневные короткие сессии по 30–40 минут, "
            "повторение базовых тем и решение типовых задач."
        )
    elif score < 85:
        strategy = (
            "Рекомендуется целенаправленная доработка пробелов: уделить больше внимания сложным темам, "
            "чередовать повторение и практику, использовать интервальное повторение."
        )
    else:
        strategy = (
            "Уровень подготовки высокий. Рекомендуется поддерживающий режим: периодическое повторение ключевых тем "
            "и решение контрольных тестов ближе к экзамену."
        )

    text = (
        f"Оценка уровня готовности: {score}%. Уровень — {level}. "
        + weak_part
        + strategy
    )

    recommendation = Recommendation(user_id=user.id, test_id=test.id, recommendation_text=text)
    db.add(recommendation)

    today = datetime.utcnow().date()
    # План повторений строим по слабым темам. Если слабых тем нет — берём первую тему предмета.
    weak_topic_ids = [tid for tid, _ in sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:3]]
    if not weak_topic_ids:
        first_topic = db.query(Topic).filter(Topic.subject_id == test.subject_id).order_by(Topic.id.asc()).first()
        if first_topic:
            weak_topic_ids = [first_topic.id]

    if weak_topic_ids:
        # Создаём 3 напоминания (повторяя первую тему при необходимости)
        for i in range(1, 4):
            topic_id = weak_topic_ids[min(i - 1, len(weak_topic_ids) - 1)]
            scheduled_date = datetime.combine(today + timedelta(days=i), datetime.min.time()) + timedelta(hours=19)
            schedule = Schedule(
                user_id=user.id,
                topic_id=topic_id,
                scheduled_date=scheduled_date,
                status="planned",
            )
            db.add(schedule)

    db.commit()
    db.refresh(test)

