from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from app.database import engine, Base, SessionLocal
from app.routers import auth, plans, apis, behavior
from app import models

Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="GPU Rent API Server",
    description="API 서버",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(plans.router)
app.include_router(apis.router)
app.include_router(behavior.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
