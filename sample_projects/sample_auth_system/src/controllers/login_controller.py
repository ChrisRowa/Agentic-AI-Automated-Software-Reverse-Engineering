"""Login HTTP controller - handles authentication requests."""
from fastapi import APIRouter, HTTPException, Depends
from src.services.auth_service import AuthService
from src.models.user import LoginRequest, TokenResponse
from src.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()
auth_service = AuthService()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = await auth_service.authenticate(
        username=request.username,
        password=request.password,
        db=db
    )
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return result


@router.post("/logout")
async def logout(token: str, db: Session = Depends(get_db)):
    """Invalidate session token."""
    await auth_service.invalidate_session(token=token, db=db)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh_token(token: str, db: Session = Depends(get_db)):
    """Refresh an expiring JWT token."""
    new_token = await auth_service.refresh_token(token=token, db=db)
    if not new_token:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return new_token
