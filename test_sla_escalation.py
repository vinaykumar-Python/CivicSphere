from datetime import datetime, timedelta
from uuid import uuid4

from app.database import SessionLocal
from app.models import Complaint
from app.sla_service import process_sla_escalations

CITIZEN_ID = 1
DEPARTMENT_ID = 1

test_tag = "SLA_TEST_" + uuid4().hex[:10]
created_ids = []

session = SessionLocal()

try:
    now = datetime.now()
    overdue_deadline = now - timedelta(hours=2)

    # Test 1: Level 0 should become Level 1.
    level_0 = Complaint(
        title=f"{test_tag}_LEVEL_0",
        description="Temporary SLA automated test.",
        category="Sanitation",
        location="Temporary test location",
        status="submitted",
        citizen_id=CITIZEN_ID,
        department_id=DEPARTMENT_ID,
        sla_deadline=overdue_deadline,
        escalation_level=0,
    )

    # Test 2: Level 1 should become Level 2 after 24 hours.
    level_1 = Complaint(
        title=f"{test_tag}_LEVEL_1",
        description="Temporary SLA automated test.",
        category="Sanitation",
        location="Temporary test location",
        status="submitted",
        citizen_id=CITIZEN_ID,
        department_id=DEPARTMENT_ID,
        sla_deadline=overdue_deadline,
        escalation_level=1,
        escalated_at=now - timedelta(hours=25),
    )

    # Test 3: Resolved complaints must not escalate.
    resolved = Complaint(
        title=f"{test_tag}_RESOLVED",
        description="Temporary SLA automated test.",
        category="Sanitation",
        location="Temporary test location",
        status="resolved",
        citizen_id=CITIZEN_ID,
        department_id=DEPARTMENT_ID,
        sla_deadline=overdue_deadline,
        escalation_level=0,
    )

    # Test 4: Rejected complaints must not escalate.
    rejected = Complaint(
        title=f"{test_tag}_REJECTED",
        description="Temporary SLA automated test.",
        category="Sanitation",
        location="Temporary test location",
        status="rejected",
        citizen_id=CITIZEN_ID,
        department_id=DEPARTMENT_ID,
        sla_deadline=overdue_deadline,
        escalation_level=0,
    )

    test_complaints = [level_0, level_1, resolved, rejected]
    session.add_all(test_complaints)
    session.commit()

    created_ids = [item.id for item in test_complaints]
    print("Temporary test complaint IDs:", created_ids)

    # Run the actual SLA processing function.
    result = process_sla_escalations()
    print("Scheduler result:", result)

    # Read the saved results.
    session.expire_all()

    results = {
        item.title: (item.status, item.escalation_level)
        for item in session.query(Complaint)
        .filter(Complaint.id.in_(created_ids))
        .all()
    }

    print("\nTEST RESULTS:")
    expected = {
        f"{test_tag}_LEVEL_0": ("submitted", 1),
        f"{test_tag}_LEVEL_1": ("submitted", 2),
        f"{test_tag}_RESOLVED": ("resolved", 0),
        f"{test_tag}_REJECTED": ("rejected", 0),
    }

    for title, expected_value in expected.items():
        actual_value = results.get(title)
        passed = actual_value == expected_value
        print(
            f"{'PASS' if passed else 'FAIL'}: {title} "
            f"| Expected: {expected_value} | Actual: {actual_value}"
        )

    if results != expected:
        raise AssertionError("One or more SLA tests failed.")

    print("\nALL FOUR SLA TESTS PASSED.")

finally:
    # Delete only the temporary complaints created by this script.
    if created_ids:
        session.rollback()
        session.query(Complaint).filter(
            Complaint.id.in_(created_ids)
        ).delete(synchronize_session=False)
        session.commit()
        print("\nTemporary test complaints cleaned up:", created_ids)

    session.close()
