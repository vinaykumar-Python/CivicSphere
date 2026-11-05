from sqlalchemy import text

from app.database import engine


def main():
    query = text("""
        SELECT
            id,
            title,
            priority,
            emergency_review_required,
            sla_deadline,
            escalation_level,
            escalated_at
        FROM complaints
        ORDER BY id DESC
        LIMIT 10
    """)

    with engine.connect() as connection:
        rows = connection.execute(query).mappings().all()

    if not rows:
        print("No complaints found.")
        return

    print("Recent complaint SLA values:\n")

    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Title: {row['title']}")
        print(f"Priority: {row['priority']}")
        print(
            "Emergency review required: "
            f"{row['emergency_review_required']}"
        )
        print(f"SLA deadline: {row['sla_deadline']}")
        print(f"Escalation level: {row['escalation_level']}")
        print(f"Escalated at: {row['escalated_at']}")
        print("-" * 40)


if __name__ == "__main__":
    main()