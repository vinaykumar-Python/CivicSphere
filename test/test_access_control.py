from sqlalchemy import select, func
from app.models import Complaint, Notification, ComplaintStatusHistory

def test_unauthenticated_cannot_access_complaints(client_for_user):
    client = client_for_user()

    response = client.get("/api/complaints/my")

    assert response.status_code == 401


def test_citizen_only_sees_own_complaints(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get("/api/complaints/my")

    assert response.status_code == 200

    complaint_ids = [
        item["id"] for item in response.json()
    ]

    assert data["complaint_one"].id in complaint_ids
    assert data["complaint_two"].id not in complaint_ids


def test_citizen_cannot_access_authority_complaints(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get("/api/authority/complaints")

    assert response.status_code == 403


def test_authority_only_sees_assigned_department(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.get("/api/authority/complaints")

    assert response.status_code == 200

    complaint_ids = [
        item["id"] for item in response.json()["items"]
    ]

    assert data["complaint_one"].id in complaint_ids
    assert data["complaint_two"].id not in complaint_ids


def test_user_only_sees_own_notifications(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get("/api/notifications/")

    assert response.status_code == 200

    notification_ids = [
        item["id"] for item in response.json()["items"]
    ]

    assert data["notification_one"].id in notification_ids
    assert data["notification_two"].id not in notification_ids


def test_user_cannot_mark_another_users_notification_read(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.patch(
        f"/api/notifications/{data['notification_two'].id}/read"
    )

    assert response.status_code == 404


def test_authority_cannot_update_another_departments_complaint(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.patch(
        f"/api/authority/complaints/{data['complaint_two'].id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 404

    db.refresh(data["complaint_two"])
    assert data["complaint_two"].status == "submitted"


def test_authority_cannot_change_closed_complaint(
    client_for_user,
    test_database,
):
    db, data = test_database
    complaint = data["complaint_one"]

    complaint.status = "resolved"
    db.commit()

    client = client_for_user(data["sanitation_authority"])

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 409

    db.refresh(complaint)
    assert complaint.status == "resolved"


def test_invalid_token_is_rejected(client_for_user):
    from fastapi.testclient import TestClient
    from app.main import app

    client = client_for_user()

    response = client.get(
        "/api/complaints/my",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert response.status_code == 401


def test_inactive_user_token_is_rejected(
    client_for_user,
    test_database,
):
    from app.security import create_access_token

    db, data = test_database

    inactive_user = data["citizen_one"]
    inactive_user.is_active = False
    db.commit()

    token = create_access_token(
        user_id=inactive_user.id,
        role=inactive_user.role,
    )

    client = client_for_user()

    response = client.get(
        "/api/complaints/my",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_valid_active_user_token_is_accepted(
    client_for_user,
    test_database,
):
    from app.security import create_access_token

    db, data = test_database
    active_user = data["citizen_one"]

    token = create_access_token(
        user_id=active_user.id,
        role=active_user.role,
    )

    client = client_for_user()

    response = client.get(
        "/api/complaints/my",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    complaint_ids = [
        item["id"] for item in response.json()
    ]

    assert data["complaint_one"].id in complaint_ids
    assert data["complaint_two"].id not in complaint_ids


def test_citizen_can_create_complaint(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.post(
        "/api/complaints/",
        json={
            "title": "Garbage collection delayed",
            "description": "Garbage has not been collected for several days.",
            "category": "garbage",
            "location": "Test Location 3",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["title"] == "Garbage collection delayed"
    assert result["category"] == "garbage"
    assert result["status"] == "submitted"
    assert result["citizen_id"] == data["citizen_one"].id
    assert result["department_id"] == data["complaint_one"].department_id


def test_new_complaint_notifies_assigned_authority(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.post(
        "/api/complaints/",
        json={
            "title": "Garbage collection delayed",
            "description": "Garbage has not been collected for several days.",
            "category": "garbage",
            "location": "Test Location 3",
        },
    )

    assert response.status_code == 200

    complaint_id = response.json()["id"]

    notification = db.query(Notification).filter(
        Notification.user_id == data["sanitation_authority"].id,
        Notification.complaint_id == complaint_id,
        Notification.notification_type == "new_complaint",
    ).first()

    assert notification is not None
    assert notification.is_read is False


def test_authority_cannot_create_complaint(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.post(
        "/api/complaints/",
        json={
            "title": "Garbage collection delayed",
            "description": "Garbage has not been collected for several days.",
            "category": "garbage",
            "location": "Test Location 3",
        },
    )

    assert response.status_code == 403

    complaint_count = db.query(Complaint).count()
    assert complaint_count == 2


def test_invalid_category_is_rejected_without_saving(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.post(
        "/api/complaints/",
        json={
            "title": "Garbage collection delayed",
            "description": "Garbage has not been collected for several days.",
            "category": "unknown category",
            "location": "Test Location 3",
        },
    )

    assert response.status_code == 422

    complaint_count = db.query(Complaint).count()
    assert complaint_count == 2


def test_citizen_can_view_own_complaint_history(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get(
        f"/api/complaints/{data['complaint_one'].id}/history"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["complaint_id"] == data["complaint_one"].id
    assert result["complaint_title"] == "Garbage near apartment"
    assert result["current_status"] == "submitted"
    assert len(result["history"]) >= 1
    assert result["history"][0]["event_type"] == "submission"
    assert result["history"][0]["changed_by_role"] == "citizen"


def test_citizen_cannot_view_another_citizens_complaint_history(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get(
        f"/api/complaints/{data['complaint_two'].id}/history"
    )

    assert response.status_code == 404


def test_authority_can_view_history_in_own_department(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.get(
        f"/api/complaints/{data['complaint_one'].id}/history"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["complaint_id"] == data["complaint_one"].id
    assert result["history"][0]["event_type"] == "submission"


def test_authority_cannot_view_history_from_another_department(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.get(
        f"/api/complaints/{data['complaint_two'].id}/history"
    )

    assert response.status_code == 404


def test_unread_only_returns_only_unread_notifications(
    client_for_user,
    test_database,
):
    db, data = test_database

    read_notification = Notification(
        user_id=data["citizen_one"].id,
        complaint_id=data["complaint_one"].id,
        title="Previously read",
        message="This notification was already read.",
        notification_type="general",
        is_read=True,
    )
    db.add(read_notification)
    db.commit()

    client = client_for_user(data["citizen_one"])

    response = client.get(
        "/api/notifications/",
        params={"unread_only": True},
    )

    assert response.status_code == 200

    result = response.json()

    assert len(result["items"]) == 1
    assert all(item["is_read"] is False for item in result["items"])
    assert result["unread_count"] == 1


def test_read_all_updates_only_current_users_notifications(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.patch("/api/notifications/read-all")

    assert response.status_code == 200
    assert response.json()["updated_count"] == 1

    own_notification = db.get(
        Notification,
        data["notification_one"].id,
    )
    other_notification = db.get(
        Notification,
        data["notification_two"].id,
    )

    assert own_notification.is_read is True
    assert other_notification.is_read is False


def test_notification_pagination_rejects_invalid_page(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get(
        "/api/notifications/",
        params={"page": 0},
    )

    assert response.status_code == 400


def test_notification_pagination_rejects_page_size_over_100(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get(
        "/api/notifications/",
        params={"page_size": 101},
    )

    assert response.status_code == 400



def test_authority_can_update_complaint_status(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    complaint = data["complaint_one"]

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200
    assert response.json()["old_status"] == "submitted"
    assert response.json()["status"] == "in_progress"

    db.refresh(complaint)
    assert complaint.status == "in_progress"


def test_status_update_creates_audit_history(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    complaint = data["complaint_one"]

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200

    history = db.scalars(
        select(ComplaintStatusHistory).where(
            ComplaintStatusHistory.complaint_id == complaint.id,
            ComplaintStatusHistory.new_status == "in_progress",
        )
    ).first()

    assert history is not None
    assert history.old_status == "submitted"
    assert history.changed_by_user_id == data["sanitation_authority"].id


def test_status_update_notifies_the_citizen(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    complaint = data["complaint_one"]

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200

    notification = db.scalars(
        select(Notification).where(
            Notification.user_id == data["citizen_one"].id,
            Notification.complaint_id == complaint.id,
            Notification.notification_type == "status_update",
        )
    ).first()

    assert notification is not None
    assert notification.is_read is False
    assert "being reviewed" in notification.message


def test_repeating_same_status_does_not_create_duplicate_history(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    complaint = data["complaint_one"]
    complaint.status = "in_progress"
    db.commit()

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "in_progress"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    history_count = db.scalar(
        select(func.count()).select_from(ComplaintStatusHistory).where(
            ComplaintStatusHistory.complaint_id == complaint.id
        )
    )

    notification_count = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.complaint_id == complaint.id,
            Notification.notification_type == "status_update",
        )
    )

    assert history_count == 0
    assert notification_count == 0


def test_invalid_status_update_is_rejected(
    client_for_user,
    test_database,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    complaint = data["complaint_one"]

    response = client.patch(
        f"/api/authority/complaints/{complaint.id}/status",
        json={"status": "pending"},
    )

    assert response.status_code == 422

    db.refresh(complaint)
    assert complaint.status == "submitted"



from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
import app.sla_service as sla_service


def test_sla_escalates_overdue_complaint_to_level_one(
    client_for_user,
    test_database,
    monkeypatch,
):
    db, data = test_database

    TestSession = sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        sla_service,
        "SessionLocal",
        TestSession,
    )

    complaint = data["complaint_one"]
    complaint.status = "submitted"
    complaint.sla_deadline = datetime.now() - timedelta(hours=1)
    complaint.escalation_level = 0
    complaint.escalated_at = None
    db.commit()

    result = sla_service.process_sla_escalations()

    db.refresh(complaint)

    assert result["level_1_escalations"] == 1
    assert complaint.escalation_level == 1
    assert complaint.escalated_at is not None

    notification = db.scalars(
        select(Notification).where(
            Notification.user_id == data["sanitation_authority"].id,
            Notification.complaint_id == complaint.id,
            Notification.notification_type == "sla_level_1",
        )
    ).first()

    assert notification is not None


def test_sla_escalates_level_one_to_level_two_after_24_hours(
    client_for_user,
    test_database,
    monkeypatch,
):
    db, data = test_database

    TestSession = sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        sla_service,
        "SessionLocal",
        TestSession,
    )

    complaint = data["complaint_one"]
    complaint.status = "in_progress"
    complaint.sla_deadline = datetime.now() - timedelta(hours=30)
    complaint.escalation_level = 1
    complaint.escalated_at = datetime.now() - timedelta(hours=25)
    db.commit()

    result = sla_service.process_sla_escalations()

    db.refresh(complaint)

    assert result["level_2_escalations"] == 1
    assert complaint.escalation_level == 2

    notification = db.scalars(
        select(Notification).where(
            Notification.user_id == data["sanitation_authority"].id,
            Notification.complaint_id == complaint.id,
            Notification.notification_type == "sla_level_2",
        )
    ).first()

    assert notification is not None


def test_sla_does_not_escalate_closed_complaints(
    client_for_user,
    test_database,
    monkeypatch,
):
    db, data = test_database

    TestSession = sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        sla_service,
        "SessionLocal",
        TestSession,
    )

    complaint = data["complaint_one"]
    complaint.status = "resolved"
    complaint.sla_deadline = datetime.now() - timedelta(hours=10)
    complaint.escalation_level = 0
    complaint.escalated_at = None
    db.commit()

    result = sla_service.process_sla_escalations()

    db.refresh(complaint)

    assert result["level_1_escalations"] == 0
    assert result["level_2_escalations"] == 0
    assert complaint.escalation_level == 0

    notification_count = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.complaint_id == complaint.id,
            Notification.notification_type.in_([
                "sla_level_1",
                "sla_level_2",
            ]),
        )
    )

    assert notification_count == 0


def test_sla_does_not_escalate_twice_after_level_two(
    client_for_user,
    test_database,
    monkeypatch,
):
    db, data = test_database

    TestSession = sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        sla_service,
        "SessionLocal",
        TestSession,
    )

    complaint = data["complaint_one"]
    complaint.status = "in_progress"
    complaint.sla_deadline = datetime.now() - timedelta(hours=50)
    complaint.escalation_level = 2
    complaint.escalated_at = datetime.now() - timedelta(hours=25)
    db.commit()

    result = sla_service.process_sla_escalations()

    db.refresh(complaint)

    assert result["level_1_escalations"] == 0
    assert result["level_2_escalations"] == 0
    assert complaint.escalation_level == 2

def test_citizen_analytics_only_counts_own_complaints(
    test_database,
    client_for_user,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get("/api/analytics/citizen")

    assert response.status_code == 200

    result = response.json()

    assert result["summary"]["total_complaints"] == 1
    assert result["by_category"] == [
        {"category": "garbage", "total": 1}
    ]


def test_authority_analytics_only_counts_own_department(
    test_database,
    client_for_user,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.get("/api/analytics/authority")

    assert response.status_code == 200

    result = response.json()

    assert result["department"]["name"] == "Sanitation Department"
    assert result["by_category"] == [
        {"category": "garbage", "total": 1}
    ]


def test_citizen_cannot_access_authority_analytics(
    test_database,
    client_for_user,
):
    db, data = test_database
    client = client_for_user(data["citizen_one"])

    response = client.get("/api/analytics/authority")

    assert response.status_code == 403


def test_authority_cannot_access_citizen_analytics_as_another_user(
    test_database,
    client_for_user,
):
    db, data = test_database
    client = client_for_user(data["sanitation_authority"])

    response = client.get("/api/analytics/citizen")

    assert response.status_code == 200
    assert response.json()["summary"]["total_complaints"] == 0