from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.evaluation import router as evaluation_router
from app.api.health import router as health_router
from app.api.mastery import router as mastery_router
from app.api.quiz import router as quiz_router
from app.api.reviews import router as reviews_router
from app.api.search import router as search_router

app = FastAPI(title="AI 学习导师", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(quiz_router)
app.include_router(reviews_router)
app.include_router(mastery_router)
app.include_router(evaluation_router)
