"""Generated message models for JSON codec testing"""

from pydantic import BaseModel


class TestUser(BaseModel):
    """Test user message model"""
    id: int
    name: str
    email: str


class UserCreated(BaseModel):
    """User created event model"""
    user_id: int
    name: str
    email: str
    timestamp: str


class UserUpdated(BaseModel):
    """User updated event model"""
    user_id: int
    name: str | None = None
    email: str | None = None
    timestamp: str


class TestEvent(BaseModel):
    """Generic test event model"""
    event_type: str
    user_id: int
    timestamp: str
    payload: dict | None = None