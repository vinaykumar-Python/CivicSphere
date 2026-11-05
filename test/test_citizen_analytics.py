from app.models import Complaint


def test_citizen_dashboard_returns_database_summary_and_recent_complaints(
    test_database,
    client_for_user,
):
    db, data = test_database
    citizen = data["citizen_one"]

    db.add_all(
        [
            Complaint(
                title="Streetlight out",
                description="The streetlight is not working.",
                category="streetlights",
                location="Test Location 3",
                status="in_progress",
                citizen_id=citizen.id,
                department_id=data["sanitation_authority"].department_id,
                escalation_level=0,
            ),
            Complaint(
                title="Water leak",
                description="Water is leaking onto the road.",
                category="water supply",
                location="Test Location 4",
                status="resolved",
                citizen_id=citizen.id,
                department_id=data["sanitation_authority"].department_id,
                escalation_level=0,
            ),
        ]
    )
    db.commit()

    response = client_for_user(citizen).get("/api/dashboard/citizen")

    assert response.status_code == 200
    result = response.json()
    assert result["summary"] == {
        "total_complaints": 3,
        "submitted": 1,
        "in_progress": 1,
        "resolved": 1,
        "rejected": 0,
    }
    assert {item["title"] for item in result["recent_complaints"]} == {
        "Garbage near apartment",
        "Streetlight out",
        "Water leak",
    }


def test_citizen_analytics_counts_only_the_signed_in_citizens_complaints(
    test_database,
    client_for_user,
):
    db, data = test_database
    citizen = data["citizen_one"]

    db.add_all(
        [
            Complaint(
                title="Streetlight out",
                description="The streetlight is not working.",
                category="streetlights",
                location="Test Location 3",
                status="in_progress",
                citizen_id=citizen.id,
                department_id=data["sanitation_authority"].department_id,
                escalation_level=0,
            ),
            Complaint(
                title="Water leak",
                description="Water is leaking onto the road.",
                category="water supply",
                location="Test Location 4",
                status="resolved",
                citizen_id=citizen.id,
                department_id=data["sanitation_authority"].department_id,
                escalation_level=0,
            ),
            Complaint(
                title="Duplicate report",
                description="This is another citizen's report.",
                category="roads",
                location="Test Location 5",
                status="submitted",
                citizen_id=data["citizen_two"].id,
                department_id=data["roads_authority"].department_id,
                escalation_level=0,
            ),
        ]
    )
    db.commit()

    response = client_for_user(citizen).get("/api/analytics/citizen")

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "total_complaints": 3,
        "submitted": 1,
        "in_progress": 1,
        "resolved": 1,
        "rejected": 0,
    }
    assert {
        item["category"]: item["total"]
        for item in response.json()["by_category"]
    } == {
        "garbage": 1,
        "streetlights": 1,
        "water supply": 1,
    }
