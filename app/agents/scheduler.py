import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from app.models import Appointment
from app.config import SessionLocal, OLLAMA_URL, LLM_MODEL

llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=LLM_MODEL,
    format="json",
    temperature=0
)

EXTRACT_DATE_PROMPT = """
Extract the appointment details from the user request.
Return a JSON with: "date_time" (e.g. "Monday 10am"), "contact" (if mentioned, else "Anonymous").

User Request: {user_input}

JSON Output:
{{
    "date_time": "...",
    "contact": "..."
}}
"""

def book_appointment(user_input: str, property_id: int = None):
    if property_id is None:
        return "ERROR: Не разбрах за кой имот искате оглед. Моля, първо намерете имота чрез търсене."

    try:
        prompt = PromptTemplate.from_template(EXTRACT_DATE_PROMPT)
        chain = prompt | llm
        response = chain.invoke({"user_input": user_input})
        data = json.loads(response.content)
        
        date_time = data.get("date_time", "Not specified")
        contact = data.get("contact", "Anonymous")

        db = SessionLocal()
        try:
            new_app = Appointment(
                property_id=property_id,
                user_contact=contact,
                date_time=date_time
            )
            db.add(new_app)
            db.commit()
            appt_id = new_app.id
        finally:
            db.close()
        
        return f"Успешно записахте час! (ID на резервация: {appt_id}). Имот ID: {property_id}. Кога: {date_time}."
        
    except Exception as e:
        return f"Error booking appointment: {str(e)}"