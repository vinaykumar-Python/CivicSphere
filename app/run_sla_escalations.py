from app.sla_service import process_sla_escalations


if __name__ == "__main__":
    result = process_sla_escalations()
    print("CivicCare AI SLA cron run completed:", result)
