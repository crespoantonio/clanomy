import pytest

@pytest.fixture
def mock_notion_service(monkeypatch):
    class MockNotionService:
        async def connect(self, token, family_id):
            return True, [{"id": "test_db_id", "title": "Test Database"}]
            
        async def connect_database(self, family_id, token, db_id, title):
            return {"database_name": title, "database_id": db_id}
            
        async def test_connection_mirror(self, family_id):
            return {"database_name": "Test Database", "page_url": "https://notion.so/test_page"}
            
        async def get_status(self, family_id):
            return True, "Connected", "Test Database", "2023-01-01T00:00:00Z"
            
        def get_family_notion_status(self, family_id):
            return {"is_connected": True, "has_valid_token": True, "database_id": "db1", "database_name": "Notion Database"}
            
        async def disconnect(self, family_id):
            return True
            
        async def mirror_transaction(self, family_id, transaction):
            pass
            
        async def validate_token(self, token):
            return True
            
        async def search_databases(self, token):
            return [{"id": "db1", "title": [{"plain_text": "Notion Database"}]}]
            
        def get_family_notion_status(self, family_id):
            return {"is_connected": True, "has_valid_token": True, "database_id": "db1"}
            
        def connect_workspace(self, family_id, token):
            return {"name": "Notion Database", "id": "12345"}
            
        def disconnect_workspace(self, family_id):
            return True
            
    mock_instance = MockNotionService()
    import src.services.notion_service
    monkeypatch.setattr("src.services.notion_service.NotionService", lambda *args, **kwargs: mock_instance)
    try:
        monkeypatch.setattr("src.api.routes.telegram.NotionService", lambda *args, **kwargs: mock_instance)
    except AttributeError:
        pass
    try:
        monkeypatch.setattr("src.services.ai_orchestrator.NotionService", lambda *args, **kwargs: mock_instance)
    except AttributeError:
        pass
    return mock_instance

def test_webhook_notion_connection_flow(app_client, mock_telegram, telegram_payload_factory, mock_notion_service):
    """[P0] Webhook should handle the Notion workspace connection flow."""
    user_id = 911
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    # 1. Provide token
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/notion connect secret_test_token", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    response_text = mock_telegram.messages[-1]["text"]
    assert "Found 1 Notion Database" in response_text or "Notion Database" in response_text
    
    # 2. Set DB
    mock_telegram.messages.clear()
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/notion setdb 1", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    assert len(mock_telegram.messages) > 0
    setdb_text = mock_telegram.messages[-1]["text"]
    assert "connected" in setdb_text.lower()
    
    # 3. Test mirror
    mock_telegram.messages.clear()
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/notion test", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    test_text = mock_telegram.messages[-1]["text"]
    assert "Successful" in test_text or "notion.so" in test_text

def test_webhook_notion_disconnect(app_client, mock_telegram, telegram_payload_factory, mock_notion_service):
    """[P1] Webhook should handle Notion disconnect command."""
    user_id = 912
    app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/start", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    mock_telegram.messages.clear()
    
    response = app_client.post(
        "/api/v1/telegram/webhook",
        json=telegram_payload_factory(text="/notion disconnect", user_id=user_id),
        headers={"X-Telegram-Bot-Api-Secret-Token": "valid-secret"}
    )
    assert response.status_code == 200
    disconnect_text = mock_telegram.messages[-1]["text"].lower()
    assert "disconnected" in disconnect_text
