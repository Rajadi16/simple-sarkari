import asyncio
from models.subscriber import Subscriber
from routers.subscribers import SubscribeRequest
from pydantic import ValidationError

def test_subscriber_schema():
    print("Testing Subscriber Schema...")
    sub = Subscriber(email="test@janvaani.in")
    assert sub.email == "test@janvaani.in"
    assert sub.is_active == True
    assert sub.created_at is not None
        
    print("Subscriber Schema tests passed!")

if __name__ == "__main__":
    test_subscriber_schema()
