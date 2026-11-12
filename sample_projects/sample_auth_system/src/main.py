"""Main application entry point."""
from fastapi import FastAPI
from src.controllers.login_controller import router as login_router
from src.controllers.user_controller import router as user_router
from src.core.database import init_database

app = FastAPI(title="Auth System")

app.include_router(login_router, prefix="/auth")
app.include_router(user_router, prefix="/users")


@app.on_event("startup")
async def startup():
    await init_database()


@app.get("/health")
def health_check():
    return {"status": "healthy"}
