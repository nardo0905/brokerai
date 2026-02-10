from sqlalchemy import text
from langchain_ollama import OllamaEmbeddings
from app.models import Base, PropertyListing
from app.config import engine, SessionLocal, OLLAMA_URL

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)

embeddings_model = OllamaEmbeddings(
    base_url=OLLAMA_URL,
    model="nomic-embed-text"
)

def add_property(title, price, location, description, features=""):
    db = SessionLocal()
    try:
        existing = db.query(PropertyListing).filter(
            PropertyListing.title == title,
            PropertyListing.location == location,
            PropertyListing.price == price,
        ).first()
        if existing:
            print(f"Skipped (duplicate): {title}")
            return False

        text_to_embed = f"{title} {location} {description} {features}"
        if len(text_to_embed) > 2000:
            text_to_embed = text_to_embed[:2000]
        vector = embeddings_model.embed_query(text_to_embed)

        new_prop = PropertyListing(
            title=title,
            price=price,
            location=location,
            description=description,
            features=features,
            embedding=vector
        )
        db.add(new_prop)
        db.commit()
        print(f"Added: {title}")
        return True
    finally:
        db.close()

def search_properties(query_text, limit=10, max_distance: float = None):
    query_vector = embeddings_model.embed_query(query_text)
    
    db = SessionLocal()
    try:
        distance_col = PropertyListing.embedding.cosine_distance(query_vector)
        
        query = db.query(PropertyListing, distance_col.label("distance")).order_by(
            distance_col
        )
        
        if max_distance is not None:
            query = query.filter(distance_col <= max_distance)
        
        rows = query.limit(limit).all()

        for prop, dist in rows:
            print(f"  📊 {prop.title[:40]:40s} | distance={dist:.4f}")
        
        return [prop for prop, _dist in rows]
    finally:
        db.close()