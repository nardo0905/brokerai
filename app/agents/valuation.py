import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from app.config import OLLAMA_URL, LLM_MODEL

llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=LLM_MODEL,
    temperature=0.1
)

VALUATION_PROMPT = """
You are a Real Estate Price Estimator.
You do NOT have access to real market data. Your assessment is a rough estimate
based on general knowledge of Bulgarian real estate prices, the listed location,
size, and features. Always caveat that this is an approximate AI estimate.

Analyze the following property listing and classify it as:
- "Good Deal" — price seems below typical market range for this type/location
- "Fair Price" — price seems within normal market range
- "Overpriced" — price seems above typical market range

Listing: {listing_text}

Output ONLY one valid JSON object like this:
{{
    "verdict": "Good Deal/Fair Price/Overpriced",
    "reasoning": "Short explanation (max 1 sentence) based on location and typical price ranges."
}}
"""


def _try_ml_valuation(listing_text: str, listed_price: float | None = None) -> str | None:
    try:
        from app.ml.predictor import predict_price, classify_price, is_trained
    except ImportError:
        return None

    if not is_trained():
        return None

    if listed_price is None:
        import re
        m = re.search(r"Price:\s*([\d.,]+)", listing_text)
        if m:
            listed_price = float(m.group(1).replace(",", ""))
        else:
            return None

    class _Listing:
        def __init__(self, text):
            self.title = text
            self.description = text
            self.features = ""
            self.location = ""
            import re as _re
            loc_m = _re.search(r"\bin\s+(.+?)\.\s*Price", text)
            if loc_m:
                self.location = loc_m.group(1)

    result = predict_price(_Listing(listing_text))
    if result is None:
        return None

    predicted = result["predicted_price"]
    verdict = classify_price(listed_price, predicted)
    reasoning = (
        f"ML model (trained on {result['model_samples']} listings, "
        f"R\u00b2={result['model_r2']:.2f}) predicts ~{predicted:,.0f} EUR for this property. "
        f"Listed at {listed_price:,.0f} EUR."
    )
    return json.dumps({"verdict": verdict, "reasoning": reasoning})


def _llm_valuation(listing_text: str) -> str:
    prompt = PromptTemplate.from_template(VALUATION_PROMPT)
    chain = prompt | llm
    response = chain.invoke({"listing_text": listing_text})
    return response.content


def evaluate_property(listing_text: str, listed_price: float | None = None) -> str:
    try:
        ml_result = _try_ml_valuation(listing_text, listed_price)
        if ml_result is not None:
            return ml_result

        return _llm_valuation(listing_text)
    except Exception as e:
        return f'{{"verdict": "Unknown", "reasoning": "Error in valuation: {str(e)}"}}'
