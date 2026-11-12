"""User management controller."""
from fastapi import APIRouter, HTTPException, Depends
from src.services.user_service import UserService
from src.models.user import UserCreate, UserResponse
from src.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()
user_service = UserService()


@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = await user_service.create_user(user_data=user_data, db=db)
    if not user:
        raise HTTPException(status_code=400, detail="User already exists")
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user profile by ID."""
    user = await user_service.get_user_by_id(user_id=user_id, db=db)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
