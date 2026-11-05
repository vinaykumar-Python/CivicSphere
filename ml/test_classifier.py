from pathlib import Path

import joblib

ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "models" / "complaint_classifier.joblib"

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        "Trained model not found. Run python ml/train_classifier.py first."
    )

model = joblib.load(MODEL_PATH)

test_complaints = [
    "Garbage has been lying near our apartment for several days",
    "The main road has several dangerous potholes",
    "Street lights are not working outside our school",
    "There is no drinking water supply in our locality",
    "Blocked drains are causing dirty water to flood the road",
    "A dangerous electrical wire is hanging over the footpath",
    "I need information about municipal office working hours",
]

print("\n===== CIVICCARE AI COMPLAINT PREDICTIONS =====\n")

for complaint in test_complaints:
    category = model.predict([complaint])[0]

    print(f"Complaint: {complaint}")
    print(f"Predicted category: {category}")
    print("-" * 60)
