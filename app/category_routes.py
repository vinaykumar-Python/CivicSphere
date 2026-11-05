from fastapi import APIRouter

router = APIRouter(
    prefix="/api/categories",
    tags=["Complaint Categories"]
)


@router.get("/")
def get_complaint_categories():
    return {
        "categories": [
            {
                "value": "garbage",
                "label": "Garbage and Waste Management",
            },
            {
                "value": "roads",
                "label": "Roads and Potholes",
            },
            {
                "value": "streetlights",
                "label": "Streetlights and Electrical Issues",
            },
            {
                "value": "water supply",
                "label": "Water Supply",
            },
            {
                "value": "drainage",
                "label": "Drainage and Sewage",
            },
            {
                "value": "public safety",
                "label": "Public Safety",
            },
            {
                "value": "other",
                "label": "Other Civic Issues",
            },
        ]
    }
