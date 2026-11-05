import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base
from app.dependencies import get_db, get_current_user
from app.main import app
from app.models import (
    User,
    Department,
    Complaint,
    Notification,
)


@pytest.fixture
def test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    sanitation = Department(
        name="Sanitation Department",
        description="Waste management",
        is_active=True,
    )

    public_works = Department(
        name="Public Works Department",
        description="Road maintenance",
        is_active=True,
    )

    db.add_all([sanitation, public_works])
    db.flush()

    citizen_one = User(
        full_name="Citizen One",
        email="citizen1@example.com",
        password_hash="test-hash",
        role="citizen",
        is_active=True,
    )

    citizen_two = User(
        full_name="Citizen Two",
        email="citizen2@example.com",
        password_hash="test-hash",
        role="citizen",
        is_active=True,
    )

    sanitation_authority = User(
        full_name="Sanitation Authority",
        email="sanitation@example.com",
        password_hash="test-hash",
        role="authority",
        is_active=True,
        department_id=sanitation.id,
    )

    roads_authority = User(
        full_name="Roads Authority",
        email="roads@example.com",
        password_hash="test-hash",
        role="authority",
        is_active=True,
        department_id=public_works.id,
    )

    db.add_all([
        citizen_one,
        citizen_two,
        sanitation_authority,
        roads_authority,
    ])
    db.flush()

    complaint_one = Complaint(
        title="Garbage near apartment",
        description="Garbage has not been collected.",
        category="garbage",
        location="Test Location 1",
        status="submitted",
        citizen_id=citizen_one.id,
        department_id=sanitation.id,
        escalation_level=0,
    )

    complaint_two = Complaint(
        title="Road pothole",
        description="A large pothole is on the road.",
        category="roads",
        location="Test Location 2",
        status="submitted",
        citizen_id=citizen_two.id,
        department_id=public_works.id,
        escalation_level=0,
    )

    db.add_all([complaint_one, complaint_two])
    db.flush()

    notification_one = Notification(
        user_id=citizen_one.id,
        complaint_id=complaint_one.id,
        title="Complaint received",
        message="Your complaint was received.",
        notification_type="general",
        is_read=False,
    )

    notification_two = Notification(
        user_id=citizen_two.id,
        complaint_id=complaint_two.id,
        title="Complaint received",
        message="Your complaint was received.",
        notification_type="general",
        is_read=False,
    )

    db.add_all([notification_one, notification_two])
    db.commit()

    data = {
        "citizen_one": citizen_one,
        "citizen_two": citizen_two,
        "sanitation_authority": sanitation_authority,
        "roads_authority": roads_authority,
        "complaint_one": complaint_one,
        "complaint_two": complaint_two,
        "notification_one": notification_one,
        "notification_two": notification_two,
    }

    yield db, data

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client_for_user(test_database):
    db, data = test_database

    def create_client(user=None):
        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        else:
            app.dependency_overrides.pop(get_current_user, None)

        return TestClient(app)

    yield create_client

    app.dependency_overrides.clear()
