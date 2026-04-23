from typing import List

from fastapi import APIRouter, Depends

from auth import DBSession, get_current_user
from models import Notification, Schedule, User
from schemas import NotificationRead, ScheduleCreate, ScheduleRead


router = APIRouter(prefix="/schedule", tags=["Schedule & Notifications"])


@router.get("/", response_model=List[ScheduleRead])
def list_schedule(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> List[ScheduleRead]:
    items = (
        db.query(Schedule)
        .filter(Schedule.user_id == current_user.id)
        .order_by(Schedule.scheduled_date.asc())
        .all()
    )
    return [ScheduleRead.model_validate(i) for i in items]


@router.post("/", response_model=ScheduleRead)
def add_schedule_item(
    item_in: ScheduleCreate,
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> ScheduleRead:
    item = Schedule(
        user_id=current_user.id,
        scheduled_date=item_in.scheduled_date,
        topic_id=item_in.topic_id,
        status=item_in.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ScheduleRead.model_validate(item)


@router.get("/notifications", response_model=List[NotificationRead])
def list_notifications(
    db: DBSession,
    current_user: User = Depends(get_current_user),
) -> List[NotificationRead]:
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [NotificationRead.model_validate(i) for i in items]

