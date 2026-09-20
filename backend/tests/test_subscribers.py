import pytest
import datetime
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from server import app
from models.subscriber import Subscriber

client = TestClient(app)

@pytest.fixture
def mock_db():
    with patch("routers.subscribers.get_db") as mock_get_db:
        db = AsyncMock()
        mock_get_db.return_value = db
        # Also need to override dependency in app
        app.dependency_overrides[mock_get_db] = lambda: db
        yield db
        app.dependency_overrides.clear()

def test_subscribe_new_user():
    # Setup mock DB
    db = AsyncMock()
    app.dependency_overrides = {}
    from lib.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    
    # Mock find_one to return None (no existing user)
    db.subscribers.find_one.return_value = None
    
    response = client.post("/api/subscribers", json={"email": "test@janvaani.in"})
    
    assert response.status_code == 200
    assert response.json() == {"status": "subscribed"}
    db.subscribers.insert_one.assert_called_once()
    
    # Clean up
    app.dependency_overrides.clear()

def test_subscribe_existing_active_user():
    db = AsyncMock()
    from lib.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    
    # Mock find_one to return active user
    db.subscribers.find_one.return_value = {"email": "test@janvaani.in", "is_active": True}
    
    response = client.post("/api/subscribers", json={"email": "test@janvaani.in"})
    
    assert response.status_code == 200
    assert response.json() == {"status": "already_subscribed"}
    db.subscribers.insert_one.assert_not_called()
    db.subscribers.update_one.assert_not_called()
    
    app.dependency_overrides.clear()

def test_subscribe_existing_inactive_user():
    db = AsyncMock()
    from lib.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    
    # Mock find_one to return inactive user
    db.subscribers.find_one.return_value = {"email": "test@janvaani.in", "is_active": False}
    
    response = client.post("/api/subscribers", json={"email": "test@janvaani.in"})
    
    assert response.status_code == 200
    assert response.json() == {"status": "resubscribed"}
    db.subscribers.update_one.assert_called_once_with(
        {"email": "test@janvaani.in"},
        {"$set": {"is_active": True}}
    )
    
    app.dependency_overrides.clear()

def test_unsubscribe_existing_user():
    db = AsyncMock()
    from lib.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    
    # Mock update_one to return success
    mock_result = MagicMock()
    mock_result.matched_count = 1
    db.subscribers.update_one.return_value = mock_result
    
    response = client.delete("/api/subscribers/test@janvaani.in")
    
    assert response.status_code == 200
    assert response.json() == {"status": "unsubscribed"}
    db.subscribers.update_one.assert_called_once_with(
        {"email": "test@janvaani.in"},
        {"$set": {"is_active": False}}
    )
    
    app.dependency_overrides.clear()

def test_unsubscribe_nonexistent_user():
    db = AsyncMock()
    from lib.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    
    # Mock update_one to return no match
    mock_result = MagicMock()
    mock_result.matched_count = 0
    db.subscribers.update_one.return_value = mock_result
    
    response = client.delete("/api/subscribers/missing@janvaani.in")
    
    assert response.status_code == 404
    assert response.json() == {"detail": "Subscriber not found"}
    
    app.dependency_overrides.clear()
