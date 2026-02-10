from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import re

from app.agents.state import AgentState
from app.rag import search_properties
from app.agents.valuation import evaluate_property
from app.agents.scheduler import book_appointment
from app.agents.scraper import build_imot_search_url, scrape_and_store
from app.config import OLLAMA_URL, LLM_MODEL

llm = ChatOllama(
    base_url=OLLAMA_URL,
    model=LLM_MODEL, 
    temperature=0.3
)

MAX_HISTORY_MESSAGES = 20

ROUTER_PROMPT = """You are a request classifier for a real estate assistant.
Classify the user's LAST message into exactly one category.
Use the recent conversation history to understand context — e.g. if the
previous messages were about searching for properties and the user now asks
"what about something cheaper?" that is still a "search".

Categories:
- "search"   : The user is looking for properties, asking about apartments, houses, prices, locations, neighborhoods, or anything related to finding/comparing real estate. Also includes follow-up questions about previously shown properties (e.g. "а по-евтино?", "something bigger?", "друго в този квартал?").
- "schedule" : The user wants to book a viewing, schedule an appointment, or arrange a meeting for a property ("оглед", "среща", "booking").
- "general"  : Greetings, small talk, thanks, questions about how you work, or anything NOT about searching/scheduling properties.

Respond with ONLY the category word, nothing else.
"""

SYSTEM_TEMPLATE = """You are BrokerAI, an intelligent real estate consultant.
Answer based ONLY on the context below.

CONTEXT:
{context}

INSTRUCTIONS:
Answer in Bulgarian. Present the properties clearly with their prices, locations and features.
"""

GENERAL_SYSTEM_PROMPT = """You are BrokerAI, a friendly real estate consultant.
You help people find properties in Bulgaria.
Answer in Bulgarian. Be helpful but concise.
If the user greets you, greet them back and ask how you can help with real estate.
If you don't have property context, suggest they search for properties.
"""

def router_node(state: AgentState):
    messages = state['messages']
    last_message = messages[-1].content
    
    print(f"🧠 Classifying intent for: {last_message[:80]}...")

    recent = messages[-6:] if len(messages) > 6 else messages
    router_messages = [SystemMessage(content=ROUTER_PROMPT)] + recent
    
    classification = llm.invoke(router_messages)
    
    intent = classification.content.strip().lower()

    if "search" in intent:
        intent = "search"
    elif "schedule" in intent:
        intent = "schedule"
    else:
        intent = "general"
    
    print(f"   ➡️ Intent: {intent}")
    return {"intent": intent}

def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "search":
        return "retrieve"
    elif intent == "schedule":
        return "schedule"
    else:
        return "chatbot_general"

def retrieve_node(state: AgentState):
    messages = state['messages']
    last_message = messages[-1]
    user_query = last_message.content
    
    print(f"🔎 User asked: {user_query}")

    results = search_properties(user_query, limit=3)

    query_lower = user_query.lower()

    from app.agents.scraper import SOFIA_NEIGHBORHOODS, PLOVDIV_NEIGHBORHOODS, VARNA_NEIGHBORHOODS, CITY_SLUGS
    all_neighborhoods = {}
    all_neighborhoods.update(SOFIA_NEIGHBORHOODS)
    all_neighborhoods.update(PLOVDIV_NEIGHBORHOODS)
    all_neighborhoods.update(VARNA_NEIGHBORHOODS)

    location_phrases = []
    for name in sorted(all_neighborhoods, key=len, reverse=True):
        if name in query_lower:
            location_phrases.append(name)
            break

    if not location_phrases:
        location_phrases = [w.lower() for w in user_query.split() if len(w) > 3]

    location_relevant = [
        r for r in results
        if any(phrase in (r.location or '').lower() for phrase in location_phrases)
    ]
    
    if len(location_relevant) < 2:
        print(f"  ⚠️ Only {len(location_relevant)} location-relevant results (of {len(results)} total) — attempting auto-scrape from imot.bg...")
        
        search_url = build_imot_search_url(user_query)
        if search_url:
            try:
                scrape_result = scrape_and_store(url=search_url, max_pages=1)
                added = scrape_result.get("added_count", 0)
                print(f"  ✅ Auto-scraped {added} new listings from imot.bg")
                
                if added > 0:
                    wider_results = search_properties(user_query, limit=10)
                    location_relevant = [
                        r for r in wider_results
                        if any(phrase in (r.location or '').lower() for phrase in location_phrases)
                    ]
                    if location_relevant:
                        results = location_relevant[:3]
                    else:
                        results = wider_results[:3]
                    print(f"  🔄 Re-search found {len(results)} relevant results")
            except Exception as e:
                print(f"  ❌ Auto-scrape failed: {e}")

    context_parts = []
    result_dict = {}
    
    if results:
        top_property_id = results[0].id
        print(f"💾 Saving Active Property ID: {top_property_id}")
        result_dict["active_property_id"] = top_property_id
        
        for i, p in enumerate(results):
            prop_desc = f"{p.title} in {p.location}. Price: {p.price} EUR. Features: {p.features}"

            if i == 0:
                try:
                    valuation_json = evaluate_property(prop_desc, listed_price=p.price)
                    if "Good Deal" in valuation_json: verdict = "Good Deal"
                    elif "Fair Price" in valuation_json: verdict = "Fair Price"
                    else: verdict = "Check Price"
                    prop_desc += f"\n   [AI ESTIMATE: {verdict} — това е приблизителна AI оценка, не професионално мнение]"
                except Exception as e:
                    print(f"  ⚠️ Valuation failed: {e}")
            
            context_parts.append(f"- ID {p.id}: {prop_desc}")
            
        context_text = "\n".join(context_parts)
    else:
        context_text = "No properties found matching the query. The user should try a more specific search or provide a direct URL to scrape."
        
    result_dict["context"] = context_text
    return result_dict

def generate_node(state: AgentState):
    context = state['context']
    messages = state['messages']
    
    final_system_prompt = SYSTEM_TEMPLATE.format(context=context)

    recent_messages = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages
    prompt_messages = [SystemMessage(content=final_system_prompt)] + recent_messages
    
    response = llm.invoke(prompt_messages)
    return {"messages": [response]}

def schedule_node(state: AgentState):
    messages = state['messages']
    active_id = state.get('active_property_id')
    user_last_msg = messages[-1].content

    id_match = re.search(r'(?:#|ID\s*|id\s*|имот\s*#?|номер\s*)(\d+)', user_last_msg, re.IGNORECASE)
    if id_match:
        requested_id = int(id_match.group(1))
        print(f"📌 User specified property ID: {requested_id}")
        active_id = requested_id
    
    print(f"📅 Schedule node triggered. Active property ID: {active_id}")
    
    if not active_id:
        return {"messages": [AIMessage(
            content="Искате оглед, но нямам активен имот. Моля, първо потърсете конкретен имот и след това поискайте оглед."
        )]}
    
    booking_result = book_appointment(user_last_msg, property_id=active_id)
    
    final_text = f"Разбрано! Задвижвам процеса за оглед на имот #{active_id}.\n\n✅ {booking_result}"
    return {
        "messages": [AIMessage(content=final_text)],
        "active_property_id": active_id,
    }

def chatbot_general_node(state: AgentState):
    messages = state['messages']

    recent_messages = messages[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else messages
    prompt_messages = [SystemMessage(content=GENERAL_SYSTEM_PROMPT)] + recent_messages
    response = llm.invoke(prompt_messages)
    return {"messages": [response]}

workflow = StateGraph(AgentState)
workflow.add_node("router", router_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("chatbot", generate_node)
workflow.add_node("schedule", schedule_node)
workflow.add_node("chatbot_general", chatbot_general_node)

workflow.set_entry_point("router")
workflow.add_conditional_edges("router", route_by_intent, {
    "retrieve": "retrieve",
    "schedule": "schedule",
    "chatbot_general": "chatbot_general",
})
workflow.add_edge("retrieve", "chatbot")
workflow.add_edge("chatbot", END)
workflow.add_edge("schedule", END)
workflow.add_edge("chatbot_general", END)

checkpointer = MemorySaver()
app_orchestrator = workflow.compile(checkpointer=checkpointer)