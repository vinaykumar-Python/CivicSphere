from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Complaint, Notification, User


# =========================================================
# SLA CONFIGURATION
# =========================================================

CHECK_INTERVAL_MINUTES = 5
LEVEL_2_DELAY_HOURS = 24

CLOSED_STATUSES = {"resolved", "rejected"}


def create_escalation_notifications(
    session,
    complaint: Complaint,
    escalation_level: int,
) -> int:
    """
    Notify all active authorities assigned to the
    complaint's department.
    """

    if not complaint.department_id:
        return 0

    authorities = session.scalars(
        select(User).where(
            User.role == "authority",
            User.department_id == complaint.department_id,
            User.is_active.is_(True),
        )
    ).all()

    if escalation_level == 1:
        title = "Complaint SLA Breached - Level 1"
        message = (
            f"Complaint #{complaint.id} has passed its original "
            f"SLA deadline and has been escalated to Level 1. "
            f"Complaint: {complaint.title}"
        )
        notification_type = "sla_level_1"

    else:
        title = "Critical SLA Escalation - Level 2"
        message = (
            f"Complaint #{complaint.id} remains unresolved 24 hours "
            f"after its Level 1 escalation. It has now reached "
            f"Level 2 escalation. Complaint: {complaint.title}"
        )
        notification_type = "sla_level_2"

    for authority in authorities:
        notification = Notification(
            user_id=authority.id,
            complaint_id=complaint.id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=False,
        )

        session.add(notification)

    return len(authorities)


# =========================================================
# SLA ESCALATION PROCESS
# =========================================================

def process_sla_escalations() -> dict:
    """
    Process overdue complaints.

    Level 0 -> Level 1:
        When the original SLA deadline passes.

    Level 1 -> Level 2:
        24 hours after the actual Level 1 escalation.

    Resolved and rejected complaints are excluded.

    Notifications are created only when an escalation
    actually occurs.
    """

    now = datetime.now()

    session = SessionLocal()

    level_1_count = 0
    level_2_count = 0

    level_1_notifications = 0
    level_2_notifications = 0

    try:
        complaints = session.scalars(
            select(Complaint)
            .where(
                Complaint.sla_deadline.is_not(None),
                Complaint.sla_deadline <= now,
                Complaint.status.notin_(CLOSED_STATUSES),
                Complaint.escalation_level < 2,
            )
            .with_for_update()
        ).all()

        for complaint in complaints:

            # -------------------------------------------------
            # LEVEL 0 -> LEVEL 1
            # -------------------------------------------------

            if complaint.escalation_level == 0:

                complaint.escalation_level = 1
                complaint.escalated_at = now

                level_1_count += 1

                level_1_notifications += (
                    create_escalation_notifications(
                        session,
                        complaint,
                        escalation_level=1,
                    )
                )

            # -------------------------------------------------
            # LEVEL 1 -> LEVEL 2
            # -------------------------------------------------

            elif complaint.escalation_level == 1:

                first_escalation_time = complaint.escalated_at

                if first_escalation_time is None:
                    first_escalation_time = complaint.sla_deadline

                level_2_deadline = (
                    first_escalation_time
                    + timedelta(hours=LEVEL_2_DELAY_HOURS)
                )

                if now >= level_2_deadline:

                    complaint.escalation_level = 2
                    complaint.escalated_at = now

                    level_2_count += 1

                    level_2_notifications += (
                        create_escalation_notifications(
                            session,
                            complaint,
                            escalation_level=2,
                        )
                    )

        # Save complaint escalations and notifications together.
        session.commit()

        result = {
            "checked_at": now.isoformat(),
            "level_1_escalations": level_1_count,
            "level_2_escalations": level_2_count,
            "level_1_notifications": level_1_notifications,
            "level_2_notifications": level_2_notifications,
        }

        print("[SLA Scheduler]", result)

        return result

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()