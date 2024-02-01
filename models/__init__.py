import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv('KARSAZ_DB_URL') or "sqlite:///../karsaz.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_model(db: Session, model: Base):
    db.add(model)
    db.commit()
    db.refresh(model)
    return model
