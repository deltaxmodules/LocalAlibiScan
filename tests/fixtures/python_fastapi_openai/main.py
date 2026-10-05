from fastapi import FastAPI

from routes.chat import router as chat_router

app = FastAPI(title="Chat Service")
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
