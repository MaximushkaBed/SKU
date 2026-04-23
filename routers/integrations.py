from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import joinedload

from auth import DBSession, require_role
from models import Notification, Schedule


router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.post(
    "/calendar/sync",
    dependencies=[Depends(require_role("teacher", "admin"))],
)
def sync_calendar(db: DBSession) -> dict:
    schedules = db.query(Schedule).filter(Schedule.status == "planned").all()
    synced = 0
    for s in schedules:
        synced += 1
    return {
        "message": "Учебная заглушка синхронизации с Google Calendar выполнена.",
        "synced_items": synced,
    }


@router.post(
    "/notifications/send",
    dependencies=[Depends(require_role("teacher", "admin"))],
)
def send_notifications(db: DBSession) -> dict:
    schedules: List[Schedule] = (
        db.query(Schedule)
        .options(joinedload(Schedule.topic))
        .filter(Schedule.status == "planned")
        .all()
    )
    created = 0
    for s in schedules:
        topic_name = s.topic.name if s.topic else f"Тема {s.topic_id}"
        message = (
            f"Напоминание: сегодня стоит повторить тему «{topic_name}». "
            f"Запланированное время: {s.scheduled_date.strftime('%d.%m.%Y %H:%M')}."
        )
        note = Notification(
            user_id=s.user_id,
            message=message,
            type="push",
            created_at=datetime.utcnow(),
        )
        db.add(note)
        created += 1
    db.commit()
    return {"message": "Учебная отправка уведомлений выполнена.", "created": created}

