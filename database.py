from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
SQLALCHEMY_DATABADE_URL = 'sqlite:///./libarary.db'
engine = create_engine(SQLALCHEMY_DATABADE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autoflush=False,autocommit= False, bind= engine)
Base = declarative_base()