def test_database_health_reports_connected_database(
    client_for_user,
    monkeypatch,
):
    import app.main as main

    monkeypatch.setattr(
        main,
        "check_database_connection",
        lambda: {"database": "civicare_test", "user": "test_user"},
    )

    response = client_for_user().get("/api/health/database")

    assert response.status_code == 200
    assert response.json() == {
        "status": "connected",
        "service": "database",
    }


def test_database_health_returns_service_unavailable_on_failure(
    client_for_user,
    monkeypatch,
):
    import app.main as main

    def fail_database_check():
        raise RuntimeError("Database is unavailable")

    monkeypatch.setattr(
        main,
        "check_database_connection",
        fail_database_check,
    )

    response = client_for_user().get("/api/health/database")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database connection failed."}
