import asyncio
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from notion_client import AsyncClient, APIResponseError
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

from src.db.models import Family, Transaction, User
from src.core.encryption import EncryptionService

logger = logging.getLogger(__name__)

def _is_transient_notion_error(exc: BaseException) -> bool:
    """
    Determines if an exception is transient and should be retried.
    Permanent errors (401 unauthorized, 404 not found, 400 validation error) are NOT retried.
    """
    if isinstance(exc, (httpx.RequestError, httpx.TimeoutException)):
        return True
    
    if isinstance(exc, APIResponseError):
        # Retry on rate limiting
        if exc.code == "rate_limited" or exc.status == 429:
            return True
        # Retry on Notion server side errors
        if exc.code in ("service_unavailable", "internal_server_error") or (exc.status and exc.status >= 500):
            return True
        # Do not retry on client/auth errors (400, 401, 403, 404)
        return False
        
    return False

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
                    "properties": list(db.get("properties", {}).keys()),
                    "properties_schema": db.get("properties", {})
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

    def _build_page_properties(
        self,
        schema: Dict[str, Any],
        concept: str,
        amount: float,
        currency: str,
        category: str,
        timestamp: datetime,
        user_name: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = {}
        
        # 1. Title property (mandatory for Notion page creation)
        title_prop_name = None
        for name, prop_info in schema.items():
            if isinstance(prop_info, dict) and prop_info.get("type") == "title":
                title_prop_name = name
                break
        if not title_prop_name:
            title_prop_name = "Concept" if "Concept" in schema else ("Name" if "Name" in schema else "Title")
        payload[title_prop_name] = {"title": [{"text": {"content": concept or "Expense"}}]}

        # 2. Iterate remaining properties in schema
        for name, prop_info in schema.items():
            if name == title_prop_name:
                continue
            p_type = prop_info.get("type") if isinstance(prop_info, dict) else prop_info
            name_lower = name.lower()

            # Amount
            if name_lower in ["amount", "cost", "price", "value", "total", "expense"]:
                if p_type == "number":
                    payload[name] = {"number": float(amount)}
                elif p_type == "rich_text":
                    payload[name] = {"rich_text": [{"text": {"content": f"{amount:.2f} {currency}"}}]}

            # Category
            elif name_lower in ["category", "tag", "tags", "type"]:
                if p_type == "select":
                    payload[name] = {"select": {"name": category}}
                elif p_type == "multi_select":
                    payload[name] = {"multi_select": [{"name": category}]}
                elif p_type == "rich_text":
                    payload[name] = {"rich_text": [{"text": {"content": category}}]}

            # Date
            elif name_lower in ["date", "timestamp", "created", "time", "when"]:
                if p_type == "date":
                    payload[name] = {"date": {"start": timestamp.isoformat()}}

            # Currency
            elif name_lower in ["currency"]:
                if p_type == "select":
                    payload[name] = {"select": {"name": currency}}
                elif p_type == "rich_text":
                    payload[name] = {"rich_text": [{"text": {"content": currency}}]}

            # Member / Author
            elif name_lower in ["member", "user", "logged by", "author", "person", "who"] and user_name:
                if p_type == "rich_text":
                    payload[name] = {"rich_text": [{"text": {"content": user_name}}]}
                elif p_type == "select":
                    payload[name] = {"select": {"name": user_name}}

        return payload

    async def _create_page_with_retry(self, notion: AsyncClient, database_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception(_is_transient_notion_error),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        ):
            with attempt:
                return await notion.pages.create(
                    parent={"database_id": database_id},
                    properties=properties
                )

    async def mirror_transaction(
        self,
        family_id: UUID,
        amount: float,
        currency: str,
        concept: str,
        category: str,
        timestamp: datetime,
        user_name: Optional[str] = None,
        transaction_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        family = self.session.get(Family, family_id)
        if not family or not family.notion_api_key or not family.notion_database_id:
            return None

        api_key = self.encryption.decrypt(family.notion_api_key)
        database_id = family.notion_database_id

        async with AsyncClient(auth=api_key) as notion:
            try:
                # Get db details to know property types and names
                db_details = await self.get_database_details(api_key, database_id)
                properties_payload = self._build_page_properties(
                    schema=db_details.get("properties_schema", {}),
                    concept=concept,
                    amount=amount,
                    currency=currency,
                    category=category,
                    timestamp=timestamp,
                    user_name=user_name
                )
                
                page = await self._create_page_with_retry(
                    notion=notion,
                    database_id=database_id,
                    properties=properties_payload
                )
                
                if transaction_id:
                    transaction = self.session.get(Transaction, transaction_id)
                    if transaction:
                        transaction.notion_page_id = page["id"]
                        transaction.notion_synced_at = datetime.now(timezone.utc)
                        self.session.add(transaction)
                        self.session.commit()

                logger.info(f"[Notion Mirror] Mirrored transaction to page {page['id']} for family {family_id}")
                return {"page_id": page["id"], "url": page.get("url"), "status": "mirrored"}
            except Exception as e:
                logger.error(f"[Notion Mirror] Failed to mirror transaction for family {family_id}: {e}")
                return None

    async def test_connection_mirror(self, family_id: UUID) -> Optional[Dict[str, Any]]:
        family = self.session.get(Family, family_id)
        if not family or not family.notion_api_key or not family.notion_database_id:
            return None

        api_key = self.encryption.decrypt(family.notion_api_key)
        database_id = family.notion_database_id
        
        async with AsyncClient(auth=api_key) as notion:
            try:
                db_details = await self.get_database_details(api_key, database_id)
                database_name = db_details.get("title", "Unknown Database")
                
                properties_payload = self._build_page_properties(
                    schema=db_details.get("properties_schema", {}),
                    concept="FamFin Test Entry",
                    amount=0.00,
                    currency="USD",
                    category="Test",
                    timestamp=datetime.now(timezone.utc),
                    user_name="System"
                )
                
                page = await notion.pages.create(
                    parent={"database_id": database_id},
                    properties=properties_payload
                )
                logger.info(f"[Notion Mirror] Created test entry in database {database_id} for family {family_id}")
                return {
                    "database_name": database_name,
                    "page_url": page.get("url"),
                    "status": "success"
                }
            except Exception as e:
                logger.error(f"[Notion Mirror] Failed to create test entry for family {family_id}: {e}")
                raise NotionServiceError(f"Test entry failed: {str(e)}")

    async def sync_pending_transactions(self, family_id: UUID, limit: int = 50) -> Dict[str, Any]:
        family = self.session.get(Family, family_id)
        if not family or not family.notion_api_key or not family.notion_database_id:
            return {"status": "not_connected", "synced": 0, "failed": 0, "total_pending": 0}

        statement = (
            select(Transaction)
            .where(Transaction.family_id == family_id)
            .where(Transaction.notion_page_id == None)  # noqa: E711
            .order_by(Transaction.timestamp.asc())
            .limit(limit)
        )
        pending_txs = self.session.exec(statement).all()
        if not pending_txs:
            return {"status": "completed", "synced": 0, "failed": 0, "total_pending": 0}

        synced_count = 0
        failed_count = 0

        for tx in pending_txs:
            try:
                # Refresh transaction to ensure real-time background task hasn't mirrored it in parallel
                self.session.refresh(tx)
                if tx.notion_page_id:
                    continue

                # Decrypt ciphertext
                decrypted_amount_str = self.encryption.decrypt(tx.amount)
                decrypted_concept = self.encryption.decrypt(tx.concept)
                
                # Parse amount & currency safely
                parts = decrypted_amount_str.split()
                try:
                    amount_val = float(parts[0]) if parts else 0.0
                except (ValueError, IndexError):
                    amount_val = 0.0
                currency_val = parts[1] if len(parts) > 1 else "USD"

                # Get user display name
                user = self.session.get(User, tx.user_id) if tx.user_id else None
                user_name = (user.full_name or user.username) if user else None

                res = await self.mirror_transaction(
                    family_id=family_id,
                    amount=amount_val,
                    currency=currency_val,
                    concept=decrypted_concept,
                    category=tx.category,
                    timestamp=tx.timestamp,
                    user_name=user_name,
                    transaction_id=tx.id
                )
                if res and res.get("status") == "mirrored":
                    synced_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"[Notion Mirror] Failed to catch-up sync transaction {tx.id}: {e}")
                failed_count += 1

        return {
            "status": "completed",
            "synced": synced_count,
            "failed": failed_count,
            "total_pending": len(pending_txs)
        }
