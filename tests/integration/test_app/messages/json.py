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


class LogEvent(BaseModel):
    """Log event for distributed logging scenario"""

    service_name: str
    level: str  # DEBUG, INFO, WARN, ERROR
    message: str
    timestamp: str
    trace_id: str | None = None


class UserAction(BaseModel):
    """User action event for fan-out broadcasting scenario"""

    action_type: str
    user_id: int
    timestamp: str
    metadata: dict | None = None


class OrderPlaced(BaseModel):
    """Order placed event for many-to-many scenario"""

    order_id: str
    user_id: int
    items: list[dict]
    total_amount: float
    timestamp: str


class PaymentProcessed(BaseModel):
    """Payment processed event for many-to-many scenario"""

    order_id: str
    payment_id: str
    amount: float
    payment_method: str
    timestamp: str


class InventoryUpdated(BaseModel):
    """Inventory updated event for many-to-many scenario"""

    order_id: str
    items_reserved: list[dict]
    timestamp: str


class OrderShipped(BaseModel):
    """Order shipped event for many-to-many scenario"""

    order_id: str
    tracking_number: str
    carrier: str
    timestamp: str
