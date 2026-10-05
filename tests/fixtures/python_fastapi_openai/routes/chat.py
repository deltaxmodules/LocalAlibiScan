from fastapi import APIRouter
from pydantic import BaseModel

from services.ai import ask

router = APIRouter(prefix="/chat")


class Question(BaseModel):
    text: str


@router.post("/")
def chat(question: Question) -> dict:
    return {"answer": ask(question.text)}


@router.get("/models")
def models() -> list[str]:
    return ["gpt-4o-mini"]
