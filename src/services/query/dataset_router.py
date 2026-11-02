import difflib
import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select
from src.db.session import engine
from src.db.models import ScheduledBill, Transaction, User
from src.core.encryption import EncryptionService
from src.services.query.models import (
    DecryptedTransaction,
    DecryptedScheduledBill,
    NormalizedQueryAST
)
from src.services.query.service import _parse_amount_string

@dataclass
class EntityMatchResult:
    target: str
    matched_candidate: Optional[str]
    score: float
    status: str  # "EXACT", "ALTERNATIVE", "NOT_FOUND"

def calculate_token_similarity(s1: str, s2: str) -> float:
    """Calculates token-based fuzzy similarity between two strings."""
    if not s1 or not s2:
        return 0.0
    
    clean1 = re.sub(r'[^\w\s]', '', s1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', s2.lower()).strip()
    
    if clean1 == clean2:
        return 1.0
    
    # Substring containment bonus
    if clean1 in clean2 or clean2 in clean1:
        return 0.9
        
    # Sequence matching
    ratio = difflib.SequenceMatcher(None, clean1, clean2).ratio()
    
    # Token set ratio
    t1 = set(clean1.split())
    t2 = set(clean2.split())
    intersection = t1.intersection(t2)
    if intersection:
        token_ratio = len(intersection) / max(len(t1), len(t2))
        return max(ratio, token_ratio)
        
    return ratio

class InMemoryEntityResolver:
    """Resolves semantic concept and category hints against decrypted tenant data."""

    def __init__(self, encryption_service: Optional[EncryptionService] = None):
        self.encryption = encryption_service or EncryptionService()

    def resolve_candidate(
        self,
        hint: str,
        candidates: List[str],
        exact_threshold: float = 0.8,
        alternative_threshold: float = 0.55
    ) -> EntityMatchResult:
        if not hint or not candidates:
            return EntityMatchResult(target=hint, matched_candidate=None, score=0.0, status="NOT_FOUND")

        best_candidate = None
        best_score = 0.0

        for cand in candidates:
            score = calculate_token_similarity(hint, cand)
            if score > best_score:
                best_score = score
                best_candidate = cand

        if best_score >= exact_threshold:
            status = "EXACT"
        elif best_score >= alternative_threshold:
            status = "ALTERNATIVE"
        else:
            status = "NOT_FOUND"

        return EntityMatchResult(
            target=hint,
            matched_candidate=best_candidate if status != "NOT_FOUND" else None,
            score=best_score,
            status=status
        )

@dataclass
class RoutedDataset:
    transactions: List[DecryptedTransaction]
    scheduled_bills: List[DecryptedScheduledBill]
    domain: str
    is_historical: bool
    is_projected: bool
    assumption_note: Optional[str] = None

class DatasetRouter:
    """Routes queries across transactions and scheduled bills based on temporal scope."""

    def __init__(self, encryption_service: Optional[EncryptionService] = None):
        self.encryption = encryption_service or EncryptionService()
        self.resolver = InMemoryEntityResolver(self.encryption)

    def route_and_fetch(
        self,
        family_id: UUID,
        ast: NormalizedQueryAST,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> RoutedDataset:
        domains = ast.filters.domains or ["expenses"]
        primary_domain = domains[0]
        is_historical = ast.temporal.is_historical
        is_projected = ast.temporal.is_projected

        transactions: List[DecryptedTransaction] = []
        bills: List[DecryptedScheduledBill] = []
        assumption_note: Optional[str] = None

        with Session(engine) as session:
            users = session.exec(select(User).where(User.family_id == family_id)).all()
            user_map = {u.id: (u.full_name or u.username or "User", f"@{u.username}" if u.username else None) for u in users}

            # 1. Domain: Bills
            if primary_domain == "bills":
                if is_historical and not is_projected:
                    # Historical bills: Fetch paid/pending scheduled bills in window + transactions with Rent/Bills
                    assumption_note = "Showing settled bill transactions and paid obligations for the past period."
                    bills = self._fetch_scheduled_bills(session, family_id, user_map, start_time, end_time, status=("paid", "pending"))
                    transactions = self._fetch_transactions(
                        session, family_id, user_map, start_time, end_time,
                        category="Rent/Bills",
                        concept_hints=ast.filters.concept_hints
                    )
                elif is_projected and not is_historical:
                    # Projected / upcoming bills: strictly pending ScheduledBill
                    bills = self._fetch_scheduled_bills(session, family_id, user_map, start_time, end_time, status="pending")
                else:
                    # Spanning or default
                    bills = self._fetch_scheduled_bills(session, family_id, user_map, start_time, end_time, status=("paid", "pending"))
                    transactions = self._fetch_transactions(session, family_id, user_map, start_time, end_time, category="Rent/Bills")

            # 2. Domain: Income
            elif primary_domain == "income":
                transactions = self._fetch_transactions(session, family_id, user_map, start_time, end_time, tx_type="income")

            # 3. Default: Expenses / Spending
            else:
                cat = ast.filters.category_hints[0] if ast.filters.category_hints else None
                transactions = self._fetch_transactions(
                    session, family_id, user_map, start_time, end_time,
                    category=cat,
                    concept_hints=ast.filters.concept_hints
                )

        return RoutedDataset(
            transactions=transactions,
            scheduled_bills=bills,
            domain=primary_domain,
            is_historical=is_historical,
            is_projected=is_projected,
            assumption_note=assumption_note
        )

    def _fetch_scheduled_bills(
        self,
        session: Session,
        family_id: UUID,
        user_map: Dict[UUID, Tuple[str, Optional[str]]],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        status: Any = "pending"
    ) -> List[DecryptedScheduledBill]:
        query = select(ScheduledBill).where(ScheduledBill.family_id == family_id)
        if isinstance(status, (list, tuple, set)):
            query = query.where(ScheduledBill.status.in_(status))
        elif status not in ("any", "all"):
            query = query.where(ScheduledBill.status == status)

        if start_time:
            query = query.where(ScheduledBill.due_date >= start_time)
        if end_time:
            query = query.where(ScheduledBill.due_date <= end_time)

        query = query.order_by(ScheduledBill.due_date.asc())
        rows = session.exec(query).all()

        results = []
        for b in rows:
            amount_str = self.encryption.decrypt(b.amount)
            concept_str = self.encryption.decrypt(b.concept)
            if not amount_str or not concept_str:
                continue
            amt, curr = _parse_amount_string(amount_str)
            u_name, u_handle = user_map.get(b.user_id, ("User", None))
            results.append(DecryptedScheduledBill(
                id=b.id,
                family_id=b.family_id,
                user_id=b.user_id,
                user_name=u_name,
                user_handle=u_handle,
                amount=amt,
                currency=curr,
                concept=concept_str,
                category=b.category or "Rent/Bills",
                due_date=b.due_date,
                status=b.status,
                paid_transaction_id=b.paid_transaction_id,
                created_at=b.created_at
            ))
        return results

    def _fetch_transactions(
        self,
        session: Session,
        family_id: UUID,
        user_map: Dict[UUID, Tuple[str, Optional[str]]],
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        category: Optional[str] = None,
        tx_type: Optional[str] = None,
        concept_hints: Optional[List[str]] = None
    ) -> List[DecryptedTransaction]:
        query = select(Transaction).where(Transaction.family_id == family_id)
        if start_time:
            query = query.where(Transaction.timestamp >= start_time)
        if end_time:
            query = query.where(Transaction.timestamp <= end_time)
        if category:
            query = query.where(Transaction.category == category)
        if tx_type:
            query = query.where(Transaction.type == tx_type)

        query = query.order_by(Transaction.timestamp.desc())
        rows = session.exec(query).all()

        results = []
        for tx in rows:
            u_name, u_handle = user_map.get(tx.user_id, ("User", None))
            amt_str = self.encryption.decrypt(tx.amount)
            conc_str = self.encryption.decrypt(tx.concept)
            if not amt_str or not conc_str:
                continue
            amt, curr = _parse_amount_string(amt_str)

            # In-memory concept filter if hints provided
            if concept_hints:
                match = self.resolver.resolve_candidate(concept_hints[0], [conc_str])
                if match.status == "NOT_FOUND":
                    continue

            results.append(DecryptedTransaction(
                id=tx.id,
                family_id=tx.family_id,
                user_id=tx.user_id,
                user_name=u_name,
                user_handle=u_handle,
                amount=amt,
                currency=curr,
                concept=conc_str,
                category=tx.category,
                timestamp=tx.timestamp,
                type=getattr(tx, "type", "expense")
            ))
        return results
