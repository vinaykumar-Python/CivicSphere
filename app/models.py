from datetime import datetime
import json
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    full_name: Mapped[str] = mapped_column(
        String(120), nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="citizen"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
    DateTime,
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
)

    # Department assigned to this authority account
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    department: Mapped["Department | None"] = relationship(
        back_populates="users"
    )

    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="citizen",
        foreign_keys="Complaint.citizen_id",
    )


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    emergency_review_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    priority: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="normal",
        server_default="normal",
    )

    matched_indicators_json: Mapped[str] = mapped_column(
        "matched_indicators",
        Text,
        nullable=False,
        default="[]",
        server_default="[]",
    )

    @property
    def matched_indicators(self) -> list[str]:
        """Return saved emergency indicators as a Python list."""
        try:
            result = json.loads(self.matched_indicators_json or "[]")
            if isinstance(result, list):
                return [
                    item for item in result
                    if isinstance(item, str)
                ]
        except (json.JSONDecodeError, TypeError):
            pass

        return []
    title: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(80), nullable=False
    )
    location: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="submitted"
    )

    citizen_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    authority_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
    DateTime,
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
)
    # Service-level agreement (SLA) tracking
    sla_deadline: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id"),
        nullable=True,
        index=True,
    )

    citizen: Mapped["User"] = relationship(
        back_populates="complaints",
        foreign_keys=[citizen_id],
    )

    authority: Mapped["User | None"] = relationship(
        foreign_keys=[authority_id],
    )

    department: Mapped["Department | None"] = relationship(
        foreign_keys=[department_id],
    )
    latitude: Mapped[float | None] = mapped_column(Float,nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(Float,nullable=True,
    )

    @property
    def department_name(self) -> str | None:
        """Return the name of the department assigned to this complaint."""
        if self.department is None:
            return None
        return self.department.name


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="department"
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("complaints.id"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    new_status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    changed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    complaint_id: Mapped[int | None] = mapped_column(
        ForeignKey("complaints.id"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )