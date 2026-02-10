"""
predictor.py – Load the trained price-prediction model and predict
the expected price for a property listing.
"""

import os
import numpy as np
import joblib

from app.ml.train_model import (
    MODEL_PATH,
    ENCODERS_PATH,
    META_PATH,
    extract_features,
    _normalise_location,
)

_model = None
_encoders = None
_meta = None


def _load():
    global _model, _encoders, _meta
    if _model is not None:
        return True
    if not os.path.exists(MODEL_PATH):
        return False
    _model = joblib.load(MODEL_PATH)
    _encoders = joblib.load(ENCODERS_PATH)
    _meta = joblib.load(META_PATH)
    return True


def reload_model():
    global _model, _encoders, _meta
    _model = _encoders = _meta = None
    return _load()


def is_trained() -> bool:
    return os.path.exists(MODEL_PATH)


def predict_price(prop) -> dict | None:
    if not _load():
        return None

    feats = extract_features(prop)
    if feats["area_sqm"] is None:
        return None

    feats["rooms"] = feats["rooms"] if feats["rooms"] is not None else -1
    feats["floor"] = feats["floor"] if feats["floor"] is not None else -1

    le_type = _encoders["property_type"]
    le_loc = _encoders["location"]

    ptype = feats["property_type"]
    type_enc = le_type.transform([ptype])[0] if ptype in le_type.classes_ else -1

    loc = feats["location"]
    loc_enc = le_loc.transform([loc])[0] if loc in le_loc.classes_ else -1

    X = np.array([[feats["area_sqm"], feats["rooms"], feats["floor"], type_enc, loc_enc]])
    predicted = float(_model.predict(X)[0])

    return {
        "predicted_price": round(predicted, 2),
        "features_used": {
            "area_sqm": feats["area_sqm"],
            "rooms": feats["rooms"],
            "floor": feats["floor"],
            "property_type": feats["property_type"],
            "location": feats["location"],
        },
        "model_samples": _meta["n_samples"] if _meta else None,
        "model_r2": _meta["mean_r2"] if _meta else None,
    }


def classify_price(listed_price: float, predicted_price: float) -> str:
    ratio = listed_price / predicted_price if predicted_price > 0 else 1.0
    if ratio < 0.85:
        return "Good Deal"
    elif ratio > 1.15:
        return "Overpriced"
    else:
        return "Fair Price"
