"""
Интеллектуальный модуль системы самоконтроля.

Алгоритм: K-means кластеризация студентов по 5 признакам.

Обоснование выбора признаков (Feature Engineering):
───────────────────────────────────────────────────────
1. avg_score       — Средний балл (0–100).
                     Прямой показатель академической успеваемости.

2. test_frequency  — Частота тестирования (тестов в неделю).
                     Отражает вовлечённость и дисциплину студента.
                     Студенты с высокой частотой тестирования в среднем
                     показывают лучшие результаты (Dunlosky et al., 2013 —
                     spaced practice effect).

3. improvement     — Динамика улучшения (разница средних последних 3 и
                     предыдущих 3 результатов).
                     Показывает обучаемость и направление движения.

4. consistency     — Стабильность результатов (100 − CV × 100, где CV —
                     коэффициент вариации).
                     Нестабильный студент может плохо справиться с
                     реальным экзаменом даже при хорошем среднем.

5. subject_breadth — Охват предметов (доля освоенных предметов от общего
                     числа в системе, 0–100).
                     Широкий охват снижает риск провала по забытым темам.

Нормализация: min-max по каждому признаку используется только для K-means,
чтобы все признаки были сопоставимы.

Позиционирование на scatter plot намеренно использует абсолютные значения
(средний балл и частота), а не нормализованные — иначе студент с 15%
и студент с 90% выглядели бы одинаково при отсутствии других данных.

Именование кластеров основано на среднем балле участников кластера
(не на центроидах нормализованного пространства), поэтому кластер
«Требует внимания» всегда содержит студентов с реально низкими оценками.
"""

from collections import defaultdict
from math import sqrt
from random import Random

from sqlalchemy.orm import Session, joinedload

from models import Question, Subject, Test, TestResult, User
from schemas import (
    ClusterCenterInfo,
    ClusterInfoRead,
    EnhancedRecommendationRead,
    ScatterPoint,
)
from services.analytics import build_student_insights, build_student_study_plan

# Максимальная частота тестирования (тестов/нед.) для нормализации scatter оси X.
# 7 — это "тест каждый день", реалистичный потолок.
_MAX_FREQ_PER_WEEK = 7.0


# ─────────────────────────── K-means core ───────────────────────────────────

def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _mean(vectors: list[tuple[float, ...]]) -> tuple[float, ...]:
    if not vectors:
        return tuple(0.0 for _ in range(5))
    size = len(vectors[0])
    return tuple(sum(v[i] for v in vectors) / len(vectors) for i in range(size))


def _kmeans(
    vectors: list[tuple[float, ...]], k: int, iterations: int = 50
) -> tuple[list[int], list[tuple[float, ...]]]:
    if not vectors:
        return [], []
    k = min(k, len(vectors))
    if len(vectors) <= k:
        labels = list(range(len(vectors)))
        return labels, vectors[:]

    rng = Random(42)
    centers = [vectors[i] for i in rng.sample(range(len(vectors)), k)]
    labels = [0] * len(vectors)

    for _ in range(iterations):
        changed = False
        for i, v in enumerate(vectors):
            best = min(range(k), key=lambda c: _distance(v, centers[c]))
            if labels[i] != best:
                labels[i] = best
                changed = True
        groups: dict[int, list[tuple[float, ...]]] = defaultdict(list)
        for label, vec in zip(labels, vectors):
            groups[label].append(vec)
        for idx in range(k):
            if groups[idx]:
                centers[idx] = _mean(groups[idx])
        if not changed:
            break
    return labels, centers


# ─────────────────────── Feature Engineering ────────────────────────────────

def _build_raw_features(
    tests: list[Test], total_subjects: int
) -> tuple[float, float, float, float, float]:
    """
    Возвращает сырой (ненормализованный) вектор признаков студента:
    (avg_score, test_frequency, improvement, consistency, subject_breadth)
    """
    if not tests:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    scores = [float(t.score or 0) for t in tests]
    avg_score = sum(scores) / len(scores)

    # Частота: тестов в неделю за активный период
    if len(tests) >= 2:
        dates = [t.created_at for t in tests]
        span_days = max(1, (max(dates) - min(dates)).days)
        test_frequency = len(tests) / (span_days / 7.0)
    else:
        # 1 тест — условно 1 тест в неделю
        test_frequency = 1.0

    # Динамика: разница средних (последние 3 vs предыдущие 3)
    recent = scores[:3]
    older = scores[3:6]
    if older:
        improvement = (sum(recent) / len(recent)) - (sum(older) / len(older))
    else:
        improvement = 0.0

    # Стабильность: 100 - CV*100 (если среднее > 0)
    if len(scores) >= 2 and avg_score > 0:
        std = sqrt(sum((s - avg_score) ** 2 for s in scores) / len(scores))
        cv = std / avg_score
        consistency = max(0.0, 100.0 * (1.0 - min(cv, 1.0)))
    else:
        # Только 1 тест → максимальная "стабильность" (нет вариации)
        consistency = 100.0

    # Охват предметов (в %)
    distinct_subjects = len(set(t.subject_id for t in tests))
    subject_breadth = min(100.0, (distinct_subjects / max(1, total_subjects)) * 100.0)

    return (avg_score, test_frequency, improvement, consistency, subject_breadth)


def _normalize(vectors: list[tuple]) -> list[tuple[float, ...]]:
    """Min-max нормализация каждого признака по всей выборке (когорте).
    Используется только для K-means — НЕ для scatter plot."""
    if not vectors:
        return []
    dims = len(vectors[0])
    mins = [min(v[i] for v in vectors) for i in range(dims)]
    maxs = [max(v[i] for v in vectors) for i in range(dims)]
    result = []
    for vec in vectors:
        norm = []
        for i, val in enumerate(vec):
            r = maxs[i] - mins[i]
            norm.append((val - mins[i]) / r if r > 0 else 0.5)
        result.append(tuple(norm))
    return result


# ─────────────────────── Cluster naming ─────────────────────────────────────

_CLUSTER_DEFINITIONS = [
    {
        "name": "Уверенный уровень",
        "summary": (
            "Стабильно высокие результаты и регулярное тестирование. "
            "Продолжайте в том же темпе — подключите более сложные вопросы "
            "и контрольные тесты по слабым предметам."
        ),
    },
    {
        "name": "В процессе подготовки",
        "summary": (
            "Есть прогресс и вовлечённость, но результаты пока неравномерны. "
            "Сфокусируйтесь на слабых темах, увеличьте частоту коротких тестов "
            "и используйте интервальное повторение."
        ),
    },
    {
        "name": "Требует внимания",
        "summary": (
            "Низкие результаты и/или нерегулярная подготовка. "
            "Рекомендуется начать с базовых тем, установить ежедневный режим "
            "из коротких тестов (5–10 мин) и обратиться за помощью к преподавателю."
        ),
    },
]


def _level_from_score(avg_score: float) -> dict:
    """
    Определяет уровень подготовки по абсолютному среднему баллу.
    Пороги соответствуют требованиям системы самоконтроля (Модуль 2):
      > 85% — высокий уровень: поддерживающая стратегия
      60–85% — средний уровень: целенаправленная доработка пробелов
      < 60%  — низкий уровень: интенсивный план подготовки
    """
    if avg_score > 85:
        return _CLUSTER_DEFINITIONS[0]
    elif avg_score >= 60:
        return _CLUSTER_DEFINITIONS[1]
    else:
        return _CLUSTER_DEFINITIONS[2]


# ─────────────────────── Ebbinghaus forgetting curve ────────────────────────

def ebbinghaus_retention(days_since_last: float, n_reviews: int) -> float:
    """
    Оценивает уровень удержания материала по модели Эббингауза:
      R = e^(-t / S)
    где:
      t — дней с момента последнего повторения по предмету
      S — стабильность памяти (растёт с числом повторений):
          S = 1 + (n_reviews - 1) * 3  (дней на «стабильность»)

    Возвращает значение от 0 (полное забывание) до 1 (свежее знание).
    При R < 0.6 рекомендуется повторение.

    Источник: Ebbinghaus H. (1885). Über das Gedächtnis.
    """
    from math import exp
    stability = max(1.0, 1.0 + (n_reviews - 1) * 3.0)
    return round(exp(-days_since_last / stability), 3)


def compute_subject_retention(tests: list) -> dict[str, dict]:
    """
    Для каждого предмета вычисляет коэффициент удержания (Эббингауз)
    и флаг «нужно повторить» (R < 0.6).

    Возвращает: { subject_name: { retention, n_tests, days_since, needs_review } }
    """
    from datetime import datetime, timezone

    by_subject: dict[str, list] = {}
    for t in tests:
        name = t.subject.name if t.subject else f"Предмет {t.subject_id}"
        by_subject.setdefault(name, []).append(t)

    now = datetime.utcnow()
    result = {}
    for subj, subj_tests in by_subject.items():
        last_date = max(t.created_at for t in subj_tests)
        days_since = max(0.0, (now - last_date).total_seconds() / 86400)
        n = len(subj_tests)
        R = ebbinghaus_retention(days_since, n)
        result[subj] = {
            "retention": R,
            "n_tests": n,
            "days_since": round(days_since, 1),
            "needs_review": R < 0.6,
        }
    return result


def _assign_cluster_names_by_members(
    k: int,
    labels: list[int],
    raw_vectors: list[tuple[float, ...]],
) -> dict[int, dict]:
    """
    Присваивает кластерам названия на основе среднего балла их участников
    с использованием абсолютных порогов (_level_from_score).

    Почему не по центроидам нормализованного пространства:
    При малом числе студентов нормализация сжимает все значения к 0.5,
    центроиды теряют смысл, и ранжирование становится случайным.

    Почему не просто по ранжированию кластеров:
    Если в системе 1 студент с 18% баллом, его кластер получит ранг 0
    и название «Уверенный» — это неверно. Абсолютные пороги решают эту проблему:
    кластер с avg=18% получит «Требует внимания» независимо от числа кластеров.
    """
    cluster_scores: dict[int, list[float]] = defaultdict(list)
    for i, label in enumerate(labels):
        cluster_scores[label].append(raw_vectors[i][0])  # raw avg_score

    mapping: dict[int, dict] = {}
    for cid, scores in cluster_scores.items():
        avg = sum(scores) / len(scores) if scores else 0.0
        mapping[cid] = _level_from_score(avg)  # абсолютные пороги, не ранжирование
    return mapping


# ─────────────────────── Public API ─────────────────────────────────────────

FEATURE_LABELS = {
    "avg_score":       "Средний балл",
    "test_frequency":  "Частота тестов (в нед.)",
    "improvement":     "Динамика",
    "consistency":     "Стабильность",
    "subject_breadth": "Охват предметов (%)",
}


def get_user_cluster(db: Session, user_id: int) -> dict:
    # Количество предметов в системе — динамически из БД
    total_subjects = db.query(Subject).count() or 1

    students: list[User] = (
        db.query(User)
        .filter(User.role == "student", User.status.is_(True))
        .all()
    )

    if not students:
        return {
            "cluster_id": 0,
            "cluster_name": "Нет данных",
            "summary": "В системе пока нет зарегистрированных студентов.",
            "peers_count": 0,
            "total_students": 0,
            "features": {k: 0.0 for k in FEATURE_LABELS},
            "feature_labels": FEATURE_LABELS,
            "scatter_points": [],
            "cluster_centers": [],
        }

    # Загружаем тесты для каждого студента
    tests_by_user: dict[int, list[Test]] = {}
    for student in students:
        tests = (
            db.query(Test)
            .options(joinedload(Test.results))
            .filter(Test.user_id == student.id)
            .order_by(Test.created_at.desc())
            .all()
        )
        tests_by_user[student.id] = tests

    # Строим сырые векторы признаков
    raw_vectors = [_build_raw_features(tests_by_user[u.id], total_subjects) for u in students]

    # Нормализуем (min-max по когорте) — только для K-means
    norm_vectors = _normalize(raw_vectors)

    # K-means: k = min(3, ceil(n/2)) чтобы избежать кластеров из 1 студента
    # при маленькой выборке
    k = min(3, max(1, (len(norm_vectors) + 1) // 2))
    labels, centers = _kmeans(norm_vectors, k=k)

    # Именуем кластеры по реальным оценкам участников
    cluster_names = _assign_cluster_names_by_members(k, labels, raw_vectors)

    # Находим индекс текущего пользователя
    user_index = next((i for i, u in enumerate(students) if u.id == user_id), None)

    if user_index is None:
        # Пользователь не студент (admin/teacher)
        overall_avg = round(sum(v[0] for v in raw_vectors) / len(raw_vectors), 2) if raw_vectors else 0.0
        return {
            "cluster_id": -1,
            "cluster_name": "Не применимо",
            "summary": (
                f"Кластеризация применяется только к студентам. "
                f"Всего в системе {len(students)} студентов."
            ),
            "peers_count": len(students),
            "total_students": len(students),
            "features": {"avg_score": overall_avg, "test_frequency": 0.0, "improvement": 0.0, "consistency": 0.0, "subject_breadth": 0.0},
            "feature_labels": FEATURE_LABELS,
            "scatter_points": [],
            "cluster_centers": [],
        }

    user_label = labels[user_index]
    peers_count = sum(1 for lbl in labels if lbl == user_label)
    raw = raw_vectors[user_index]

    # ── Scatter plot ──────────────────────────────────────────────────────────
    # Используем АБСОЛЮТНЫЕ значения (не нормализованные), чтобы позиция
    # студента была понятной даже при 1 пользователе в системе:
    #   X = avg_score / 100        → ось "Результативность" (0–100%)
    #   Y = test_frequency / MAX   → ось "Активность" (тестов в неделю)
    #
    # Такой подход даёт значимую позицию без сравнения с другими:
    # студент с 18% будет слева внизу, с 85% — справа вверху.
    scatter_points = []
    for i, (student, label) in enumerate(zip(students, labels)):
        rv = raw_vectors[i]
        scatter_points.append(
            ScatterPoint(
                x=round(min(rv[1] / _MAX_FREQ_PER_WEEK, 1.0), 4),  # активность
                y=round(rv[0] / 100.0, 4),                           # результативность
                cluster_id=int(label),
                is_self=(student.id == user_id),
            )
        )

    # Центры кластеров в тех же абсолютных координатах
    # (средние значения членов кластера, не нормализованные центроиды)
    cluster_centers = []
    raw_by_cluster: dict[int, list[tuple[float, ...]]] = defaultdict(list)
    for i, label in enumerate(labels):
        raw_by_cluster[label].append(raw_vectors[i])

    for idx in range(k):
        members = raw_by_cluster.get(idx, [])
        if not members:
            continue
        cx_raw = sum(v[1] for v in members) / len(members)  # avg freq
        cy_raw = sum(v[0] for v in members) / len(members)  # avg score
        defn = cluster_names.get(idx, _CLUSTER_DEFINITIONS[-1])
        cluster_centers.append(
            ClusterCenterInfo(
                cluster_id=int(idx),
                cluster_name=defn["name"],
                x=round(min(cx_raw / _MAX_FREQ_PER_WEEK, 1.0), 4),
                y=round(cy_raw / 100.0, 4),
            )
        )

    defn = cluster_names.get(user_label, _CLUSTER_DEFINITIONS[-1])

    return {
        "cluster_id": int(user_label),
        "cluster_name": defn["name"],
        "summary": defn["summary"],
        "peers_count": int(peers_count),
        "total_students": len(students),
        "features": {
            "avg_score":       round(raw[0], 2),
            "test_frequency":  round(raw[1], 2),
            "improvement":     round(raw[2], 2),
            "consistency":     round(raw[3], 2),
            "subject_breadth": round(raw[4], 2),
        },
        "feature_labels": FEATURE_LABELS,
        "scatter_points": scatter_points,
        "cluster_centers": cluster_centers,
    }


# ─────────────────────── Enhanced recommendations ───────────────────────────

def build_enhanced_recommendations(db: Session, user_id: int) -> list[EnhancedRecommendationRead]:
    tests = (
        db.query(Test)
        .options(
            joinedload(Test.subject),
            joinedload(Test.results).joinedload(TestResult.question).joinedload(Question.topic),
        )
        .filter(Test.user_id == user_id)
        .order_by(Test.created_at.desc())
        .all()
    )
    insights = build_student_insights(tests)
    plan = build_student_study_plan(insights)

    avg_score = insights.average_score or 0.0
    weak_topics = ", ".join(t.topic_name for t in insights.priority_topics[:3]) or "—"

    # Выбираем технику в зависимости от уровня
    if avg_score < 60:
        technique = "Метод Эббингауза: повторяйте тему через 1 → 3 → 7 → 14 дней — это предотвращает забывание до экзамена"
        first_step = f"Пройти быстрый тест по самой слабой теме ({weak_topics}) — 10 вопросов, не более 15 минут"
    elif avg_score < 85:
        technique = "Техника Помодоро: 25 минут работы → 5 минут перерыв → повторить 4 раза → длинный перерыв 20 мин"
        first_step = f"Пройти тест по теме «{insights.priority_topics[0].topic_name if insights.priority_topics else weak_topics}» и сравнить с предыдущим результатом"
    else:
        technique = "Интервальное повторение (Anki): добавьте карточки по изученным темам и повторяйте по расписанию системы"
        first_step = "Пройти контрольный полный тест по наиболее давно изученному предмету"

    items: list[EnhancedRecommendationRead] = [
        EnhancedRecommendationRead(
            title="Фокус следующей недели",
            reason=insights.motivation_message,
            actions=[
                first_step,
                f"Слабые темы для повторения: {weak_topics}",
                technique,
            ],
            confidence=0.78 if tests else 0.35,
        ),
        EnhancedRecommendationRead(
            title="Персональный план на 7 дней",
            reason=plan.overview,
            actions=[f"{item.day_label}: {item.title}" for item in plan.items[:5]],
            confidence=0.72 if tests else 0.3,
        ),
    ]

    # Блок Эббингауза — только если есть тесты по нескольким предметам
    if tests:
        retention_data = compute_subject_retention(tests)
        needs_review = [(subj, info) for subj, info in retention_data.items() if info["needs_review"]]
        if needs_review:
            subj_list = ", ".join(s for s, _ in needs_review[:3])
            items.append(
                EnhancedRecommendationRead(
                    title="Кривая забывания Эббингауза",
                    reason=(
                        f"По {len(needs_review)} предмет(ам) коэффициент удержания материала "
                        f"упал ниже 60% — материал начинает забываться. "
                        f"Формула: R = e^(−t/S), где t — дней с последнего теста."
                    ),
                    actions=[
                        f"Срочно повторить: {subj_list}",
                        "Откройте Anki (apps.ankiweb.net) и создайте карточки по этим темам",
                        "Интервал повторения: 1 день → 3 дня → 1 неделя → 2 недели → 1 месяц",
                    ],
                    confidence=0.88,
                )
            )

    return items


# ─────────────────────── AI assistant ───────────────────────────────────────

def ai_assistant_reply(db: Session, user_id: int, message: str) -> dict:
    text = (message or "").strip().lower()
    cluster_data = get_user_cluster(db, user_id)
    cluster_name = cluster_data["cluster_name"]
    features = cluster_data["features"]
    recommendations = build_enhanced_recommendations(db, user_id)

    if any(word in text for word in ("кластер", "cluster", "группа", "категория")):
        reply = (
            f"Вы в кластере «{cluster_name}». "
            f"Средний балл: {features['avg_score']}%, "
            f"частота тестов: {features['test_frequency']:.1f}/нед., "
            f"стабильность: {features['consistency']:.0f}%."
        )
    elif any(word in text for word in ("что делать", "план", "рекомендац", "совет")):
        top = recommendations[0]
        reply = f"{top.title}: {top.reason} Первый шаг: {top.actions[0]}."
    elif any(word in text for word in ("слаб", "ошиб", "тема", "предмет")):
        top = recommendations[0]
        reply = f"По результатам анализа: {top.actions[1]}."
    elif any(word in text for word in ("тренд", "динамик", "прогресс", "улучш")):
        trend = features.get("improvement", 0)
        sign = "+" if trend >= 0 else ""
        reply = (
            f"Динамика ваших результатов: {sign}{trend:.1f}% "
            f"(сравнение последних 3 тестов с предыдущими 3). "
            + ("Идёт улучшение!" if trend > 0 else "Нужно поработать над системностью." if trend < 0 else "Результаты стабильны.")
        )
    elif any(word in text for word in ("стабил", "consistency")):
        reply = (
            f"Стабильность ваших результатов: {features['consistency']:.0f}% "
            f"(100% = все тесты с одинаковым результатом, ниже = больше разброс)."
        )
    else:
        reply = (
            "Я AI-ассистент по подготовке к экзаменам. "
            "Могу объяснить ваш кластер, показать динамику, рассказать что делать дальше."
        )

    hints = [
        "В каком я кластере?",
        "Что делать на этой неделе?",
        "Какая у меня динамика?",
        "Какие темы слабые?",
    ]
    return {"reply": reply, "hints": hints}
