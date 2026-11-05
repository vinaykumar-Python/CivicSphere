import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import Notification, User


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)


@router.get("/")
def get_notifications(
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if page < 1 or page_size < 1 or page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid pagination values.",
            )   
    query = select(Notification).where(
        Notification.user_id == current_user.id
    )

    if unread_only:
        query = query.where(
            Notification.is_read.is_(False)
        )

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    unread_count = db.scalar(
        select(func.count()).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ) or 0

    notifications = db.scalars(
        query.order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "items": [
            {
                "id": item.id,
                "complaint_id": item.complaint_id,
                "title": item.title,
                "message": item.message,
                "notification_type": item.notification_type,
                "is_read": item.is_read,
                "created_at": item.created_at,
            }
            for item in notifications
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": (
                (total + page_size - 1) // page_size
            ),
            "has_next": (
                page < (total + page_size - 1) // page_size
            ),
            "has_previous": page > 1 and total > 0,
        },
        "unread_count": unread_count,
    }


@router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.scalar(
        select(func.count()).where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    ) or 0

    return {"unread_count": count}


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    if notification.is_read:
        return {
            "message": "Notification is already marked as read.",
            "notification_id": notification.id,
            "is_read": True,
        }

    try:
        notification.is_read = True
        db.commit()

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Failed to mark notification %s as read for user %s.",
            notification_id,
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update notification.",
        ) from exc

    return {
        "message": "Notification marked as read.",
        "notification_id": notification.id,
        "is_read": True,
    }


@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = db.execute(
            update(Notification)
            .where(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )

        updated_count = result.rowcount or 0

        db.commit()

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Failed to mark all notifications as read for user %s.",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update notifications.",
        ) from exc

    return {
        "message": "All notifications marked as read.",
        "updated_count": updated_count,
    }