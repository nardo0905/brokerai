"""
train_model.py – Extract features from the properties table and train a
GradientBoosting regression model that predicts the listed price.

Usage (inside the running container):
    python -m app.ml.train_model

Or triggered via the /api/ml/train endpoint.
"""

import re
import os
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder
import joblib

from app.config import SessionLocal
from app.models import PropertyListing

MODEL_DIR = os.path.join(os.path.dirname(__file__), "artefacts")
MODEL_PATH = os.path.join(MODEL_DIR, "price_model.joblib")
ENCODERS_PATH = os.path.join(MODEL_DIR, "label_encoders.joblib")
META_PATH = os.path.join(MODEL_DIR, "meta.joblib")


_AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:кв\.?\s*м|m2|sq\.?\s*m|квм)", re.IGNORECASE)
_ROOMS_RE = re.compile(
    r"(\d+)\s*(?:-?\s*(?:стаен|стайн|стаи|rooms?|стая)|"
    r"(?:едностаен|двустаен|тристаен|четиристаен|многостаен|мезонет|ателие|студио))",
    re.IGNORECASE,
)
_ROOMS_WORD = {
    "студио": 1, "ателие": 1, "едностаен": 1,
    "двустаен": 2, "тристаен": 3, "четиристаен": 4,
    "многостаен": 5, "мезонет": 4,
}
_FLOOR_RE = re.compile(r"(?:етаж|floor|ет\.?)\s*(\d+)", re.IGNORECASE)
_PROP_TYPE = {
    "апартамент": "apartment", "стая": "room", "къща": "house",
    "мезонет": "apartment", "ателие": "apartment", "студио": "apartment",
    "парцел": "land", "гараж": "garage", "офис": "office",
    "магазин": "shop", "заведение": "shop", "склад": "warehouse",
    "етаж от къща": "house",
}


def _extract_area(text: str) -> float | None:
    m = _AREA_RE.search(text)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _extract_rooms(text: str) -> int | None:
    text_lower = text.lower()
    for word, num in _ROOMS_WORD.items():
        if word in text_lower:
            return num
    m = _ROOMS_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _extract_floor(text: str) -> int | None:
    m = _FLOOR_RE.search(text)
    if m:
        return int(m.group(1))
    return None


def _extract_property_type(text: str) -> str:
    text_lower = text.lower()
    for kw, ptype in _PROP_TYPE.items():
        if kw in text_lower:
            return ptype
    return "other"


def _normalise_location(location: str) -> str:
    loc = location.strip().lower()
    for suffix in [", bulgaria", ", българия"]:
        loc = loc.replace(suffix, "")
    return loc.strip()


def extract_features(prop: PropertyListing) -> dict:
    blob = f"{prop.title} {prop.description} {prop.features or ''}"
    return {
        "area_sqm": _extract_area(blob),
        "rooms": _extract_rooms(blob),
        "floor": _extract_floor(blob),
        "property_type": _extract_property_type(blob),
        "location": _normalise_location(prop.location),
    }

def _build_dataset():
    db = SessionLocal()
    try:
        props = db.query(PropertyListing).all()
    finally:
        db.close()

    rows, prices = [], []
    skipped = 0
    for p in props:
        feats = extract_features(p)
        if feats["area_sqm"] is None:
            skipped += 1
            continue

        feats["rooms"] = feats["rooms"] if feats["rooms"] is not None else -1
        feats["floor"] = feats["floor"] if feats["floor"] is not None else -1
        rows.append(feats)
        prices.append(p.price)

    return rows, np.array(prices), skipped

def train() -> dict:
    rows, y, skipped = _build_dataset()
    n = len(rows)
    if n < 10:
        return {
            "status": "error",
            "message": f"Not enough usable listings to train ({n} usable, {skipped} skipped). "
                       f"Need at least 10 listings with extractable area (m²). "
                       f"Scrape more properties first.",
        }

    le_type = LabelEncoder()
    le_loc = LabelEncoder()
    types = le_type.fit_transform([r["property_type"] for r in rows])
    locs = le_loc.fit_transform([r["location"] for r in rows])

    X = np.column_stack([
        [r["area_sqm"] for r in rows],
        [r["rooms"] for r in rows],
        [r["floor"] for r in rows],
        types,
        locs,
    ])

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X, y)

    cv_folds = min(5, n)
    if cv_folds >= 2:
        scores = cross_val_score(model, X, y, cv=cv_folds, scoring="r2")
        mean_r2 = float(scores.mean())
    else:
        mean_r2 = None

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump({"property_type": le_type, "location": le_loc}, ENCODERS_PATH)
    joblib.dump({
        "n_samples": n,
        "skipped": skipped,
        "mean_r2": mean_r2,
        "feature_names": ["area_sqm", "rooms", "floor", "property_type_enc", "location_enc"],
    }, META_PATH)

    print(f"✅ Model trained on {n} samples (skipped {skipped}). "
          f"CV R²={mean_r2:.3f}" if mean_r2 is not None else "")

    return {
        "status": "success",
        "samples_used": n,
        "samples_skipped": skipped,
        "cv_r2": round(mean_r2, 4) if mean_r2 is not None else None,
        "model_path": MODEL_PATH,
    }


if __name__ == "__main__":
    result = train()
    print(result)
