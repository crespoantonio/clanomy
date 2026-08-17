import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session
from notion_client import AsyncClient, APIResponseError

from src.db.models import Family
from src.core.encryption import EncryptionService

class NotionAuthError(Exception):
    """Raised when the provided Notion API token is invalid or unauthorized."""
    pass

class NotionDatabaseNotFoundError(Exception):
    """Raised when the specified database ID is not found or inaccessible."""
    pass

class NotionServiceError(Exception):
    """Generic Notion API error."""
    pass

class NotionService:
    def __init__(self, session: Session):
        self.session = session
        self.encryption = EncryptionService()

    async def validate_token(self, api_key: str) -> bool:
        """Verifies that the provided token is valid by querying the Notion Users API."""
        async with AsyncClient(auth=api_key) as notion:
            try:
                await notion.users.me()
                return True
            except APIResponseError as e:
                if e.code == "unauthorized":
                    return False
                raise NotionServiceError(f"Notion API error: {e.message}")
            except Exception as e:
                raise NotionServiceError(f"Failed to communicate with Notion API: {e}")

    async def search_databases(self, api_key: str) -> List[Dict[str, Any]]:
        """Searches for all database objects accessible by the integration."""
        async with AsyncClient(auth=api_key) as notion:
            try:
                response = await notion.search(filter={"property": "object", "value": "database"})
                databases = []
                for db in response.get("results", []):
                    title_list = db.get("title", [])
                    title_text = "".join([t.get("plain_text", "") for t in title_list]) or "Untitled Database"
                    databases.append({
                        "id": db.get("id"),
                        "title": title_text,
                        "url": db.get("url"),
                        "properties": list(db.get("properties", {}).keys())
                    })
                return databases
            except APIResponseError as e:
                if e.code == "unauthorized":
                    raise NotionAuthError("Invalid Notion API key or token.")
                raise NotionServiceError(f"Notion API error: {e.message}")
            except Exception as e:
                raise NotionServiceError(f"Failed to communicate with Notion API: {e}")

    async def get_database_details(self, api_key: str, database_id: str) -> Dict[str, Any]:
        """Retrieves specific database metadata."""
        async with AsyncClient(auth=api_key) as notion:
            try:
                db = await notion.databases.retrieve(database_id=database_id)
                title_list = db.get("title", [])
                title_text = "".join([t.get("plain_text", "") for t in title_list]) or "Untitled Database"
                return {
                    "id": db.get("id"),
                    "title": title_text,
                    "url": db.get("url"),
                    "properties": list(db.get("properties", {}).keys())
                }
            except APIResponseError as e:
                if e.code == "object_not_found" or e.status == 404:
                    raise NotionDatabaseNotFoundError(f"Database {database_id} not found.")
                if e.code == "unauthorized":
                    raise NotionAuthError("Invalid Notion API key or token.")
                raise NotionServiceError(f"Notion API error: {e.message}")
            except Exception as e:
                raise NotionServiceError(f"Failed to communicate with Notion API: {e}")

    async def connect_database(self, family_id: UUID, api_key: str, database_id: str, database_name: Optional[str] = None) -> Dict[str, Any]:
        """Connects the database to the family and encrypts the key."""
        # Validate token and target database access
        details = await self.get_database_details(api_key, database_id)
        if not database_name:
            database_name = details["title"]
        
        # We assume the caller runs this within an async context but self.session is a sync Session
        # In a real async DB context this would be an async session, but currently sqlmodel Session is used
        family = self.session.get(Family, family_id)
        if not family:
            raise ValueError(f"Family {family_id} not found")

        encrypted_token = self.encryption.encrypt(api_key)
        family.notion_api_key = encrypted_token
        family.notion_database_id = database_id
        family.notion_database_name = database_name
        family.notion_connected_at = datetime.now(timezone.utc)
        self.session.add(family)
        self.session.commit()
        
        return {
            "database_id": database_id,
            "database_name": database_name,
            "connected_at": family.notion_connected_at
        }

    def disconnect_workspace(self, family_id: UUID) -> bool:
        """Disconnects Notion workspace."""
        family = self.session.get(Family, family_id)
        if not family:
            return False

        family.notion_api_key = None
        family.notion_database_id = None
        family.notion_database_name = None
        family.notion_connected_at = None
        self.session.add(family)
        self.session.commit()
        return True

    def get_family_notion_status(self, family_id: UUID) -> Dict[str, Any]:
        """Returns the connection status for a family."""
        family = self.session.get(Family, family_id)
        if not family:
            return {"is_connected": False, "has_valid_token": False}
            
        is_connected = bool(family.notion_api_key and family.notion_database_id)
        return {
            "is_connected": is_connected,
            "database_id": family.notion_database_id,
            "database_name": family.notion_database_name,
            "connected_at": family.notion_connected_at,
            "has_valid_token": bool(family.notion_api_key)
        }
