from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Complaint, Notification
from app.sla_service import process_sla_escalations


def test_sla_escalations_run_against_isolated_test_database(
    test_database,
    monkeypatch,
):
    import app.sla_service as sla_service

    db, data = test_database
    test_session_factory = sessionmaker(
        bind=db.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        sla_service,
        "SessionLocal",
        test_session_factory,
    )

    now = datetime.now()
    overdue_deadline = now - timedelta(hours=26)
    test_complaints = [
        Complaint(
            title="Overdue level zero",
            description="Test complaint for first-level escalation.",
            category="Sanitation",
            location="Test location",
            status="submitted",
            citizen_id=data["citizen_one"].id,
            department_id=data["sanitation_authority"].department_id,
            sla_deadline=overdue_deadline,
            escalation_level=0,
        ),
        Complaint(
            title="Overdue level one",
            description="Test complaint for second-level escalation.",
            category="Sanitation",
            location="Test location",
            status="submitted",
            citizen_id=data["citizen_one"].id,
            department_id=data["sanitation_authority"].department_id,
            sla_deadline=overdue_deadline,
            escalation_level=1,
            escalated_at=now - timedelta(hours=25),
        ),
        Complaint(
            title="Resolved overdue complaint",
            description="Closed complaints must not escalate.",
            category="Sanitation",
            location="Test location",
            status="resolved",
            citizen_id=data["citizen_one"].id,
            department_id=data["sanitation_authority"].department_id,
            sla_deadline=overdue_deadline,
            escalation_level=0,
        ),
        Complaint(
            title="Rejected overdue complaint",
            description="Closed complaints must not escalate.",
            category="Sanitation",
            location="Test location",
            status="rejected",
            citizen_id=data["citizen_one"].id,
            department_id=data["sanitation_authority"].department_id,
            sla_deadline=overdue_deadline,
            escalation_level=0,
        ),
    ]

    db.add_all(test_complaints)
    db.commit()
    complaint_ids = [complaint.id for complaint in test_complaints]

    result = process_sla_escalations()

    db.expire_all()
    saved_complaints = db.scalars(
        select(Complaint).where(Complaint.id.in_(complaint_ids))
    ).all()
    saved_by_title = {
        complaint.title: (complaint.status, complaint.escalation_level)
        for complaint in saved_complaints
    }
    notification_types = db.scalars(
        select(Notification.notification_type).where(
            Notification.complaint_id.in_(complaint_ids)
        )
    ).all()

    assert result["level_1_escalations"] == 1
    assert result["level_2_escalations"] == 1
    assert saved_by_title == {
        "Overdue level zero": ("submitted", 1),
        "Overdue level one": ("submitted", 2),
        "Resolved overdue complaint": ("resolved", 0),
        "Rejected overdue complaint": ("rejected", 0),
    }
    assert sorted(notification_types) == [
        "sla_level_1",
        "sla_level_2",
    ]

    second_result = process_sla_escalations()

    assert second_result["level_1_escalations"] == 0
    assert second_result["level_2_escalations"] == 0
