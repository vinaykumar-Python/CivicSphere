from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    category: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=255)

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("title", "description", "category", "location")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot contain only spaces.")

        return value

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "Both latitude and longitude must be provided together."
            )

        return self


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: str
    location: str

    latitude: float | None = None
    longitude: float | None = None

    status: str
    citizen_id: int
    authority_id: int | None
    department_id: int | None
    department_name: str | None = None

    created_at: datetime
    updated_at: datetime

    # Emergency screening information
    emergency_review_required: bool = False
    matched_indicators: list[str] = Field(default_factory=list)
    priority: str = "normal"

    emergency_message: str = (
        "No emergency screening result was supplied."
    )