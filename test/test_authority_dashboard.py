from datetime import datetime, timedelta

from app.models import Complaint


def test_authority_dashboard_counts_overdue_open_complaints_by_department(
    test_database,
    client_for_user,
):
    db, data = test_database
    authority = data["sanitation_authority"]
    citizen = data["citizen_one"]
    other_department = data["roads_authority"].department_id
    overdue_deadline = datetime.now() - timedelta(days=1)

    db.add_all(
        [
            Complaint(
                title="Unresolved overdue issue",
                description="Still waiting for attention.",
                category="roads",
                location="Sanitation area",
                status="in_progress",
                citizen_id=citizen.id,
                department_id=authority.department_id,
                sla_deadline=overdue_deadline,
            ),
            Complaint(
                title="Resolved overdue issue",
                description="Already resolved.",
                category="roads",
                location="Sanitation area",
                status="resolved",
                citizen_id=citizen.id,
                department_id=authority.department_id,
                sla_deadline=overdue_deadline,
            ),
            Complaint(
                title="Another department issue",
                description="Belongs to a different team.",
                category="roads",
                location="Roads area",
                status="submitted",
                citizen_id=data["citizen_two"].id,
                department_id=other_department,
                sla_deadline=overdue_deadline,
            ),
        ]
    )
    db.commit()

    response = client_for_user(authority).get("/api/dashboard/authority")

    assert response.status_code == 200
    result = response.json()
    assert result["summary"] == {
        "total_complaints": 3,
        "submitted": 1,
        "in_progress": 1,
        "resolved": 1,
        "rejected": 0,
        "overdue": 1,
    }
    assert {item["title"] for item in result["recent_complaints"]} == {
        "Garbage near apartment",
        "Unresolved overdue issue",
        "Resolved overdue issue",
    }
