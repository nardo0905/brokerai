from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class PropertyListing(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    features = Column(Text) # JSON string или CSV с екстри
    
    # Тук се пази "смысъла" на имота като вектор (768 измерения за nomic-embed-text)
    embedding = Column(Vector(768)) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, nullable=False) # За кой имот е
    user_contact = Column(String, nullable=False) # Телефон/Име на клиента
    date_time = Column(String, nullable=False)    # Кога (пазим като текст за по-лесно: "Утре в 10:00")
    status = Column(String, default="Confirmed")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())