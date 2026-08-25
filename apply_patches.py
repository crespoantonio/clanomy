import re
import asyncio
from pathlib import Path

# 1. Update tests/api/conftest.py
conftest_path = Path('tests/api/conftest.py')
conftest_code = conftest_path.read_text(encoding='utf-8')
conftest_code = conftest_code.replace("text_lower = text.lower()", "text_lower = (text or '').lower()")
conftest_path.write_text(conftest_code, encoding='utf-8')

# 2. Update src/services/ai_orchestrator.py
orch_path = Path('src/services/ai_orchestrator.py')
orch_code = orch_path.read_text(encoding='utf-8')

# Fix _format_currency
orch_code = orch_code.replace('curr_upper = currency.upper()', 'curr_upper = (currency or "USD").upper()')
orch_code = orch_code.replace('abs_amt = abs(amount)', 'abs_amt = abs(amount or 0.0)')
orch_code = orch_code.replace('sign = "-" if amount < 0 else ("+" if show_sign else "")', 'sign = "-" if (amount or 0.0) < 0 else ("+" if show_sign and (amount or 0.0) > 0 else "")')

# Fix docstring of _persist_transaction
orch_code = orch_code.replace('        Runs inside a separate thread', '        :param tx_type: Type of transaction (expense/income)\n        Runs inside a separate thread')
orch_code = orch_code.replace('type=tx_type,', 'tx_type=tx_type,')

# Fix _get_monthly_cash_flow_snapshot
# change <= end_of_month to < next_month
orch_code = orch_code.replace('Transaction.timestamp <= end_of_month', 'Transaction.timestamp < next_month')
# change type to tx_type in getattr
orch_code = orch_code.replace('getattr(tx, "type", "expense")', 'getattr(tx, "tx_type", "expense")')
# We will optimize the loop by using a list comprehension or we just leave it for now and optimize later if it's too complex. 
# Wait, I promised to patch it. Let's make the decryption use ThreadPoolExecutor.
# Actually, since it's already in asyncio.to_thread, we can just use ThreadPoolExecutor inside it.
import textwrap
optimized_loop = textwrap.dedent('''\
            from concurrent.futures import ThreadPoolExecutor
            def _decrypt_tx(tx):
                try:
                    decrypted_amount_str = self.encryption_service.decrypt(tx.amount)
                    if not decrypted_amount_str:
                        return None
                    parts = decrypted_amount_str.strip().split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    tx_type = getattr(tx, "tx_type", "expense") or "expense"
                    return (curr, tx_type, amt)
                except Exception as e:
                    logger.warning(f"Failed to decrypt transaction {tx.id} for cash flow snapshot: {e}")
                    return None
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(_decrypt_tx, transactions)
            
            for res in results:
                if res:
                    curr, tx_type, amt = res
                    if curr == primary_currency.upper():
                        if tx_type == "income":
                            total_in += amt
                        else:
                            total_out += amt
''')
# Replace the original loop
orig_loop = textwrap.dedent('''\
            for tx in transactions:
                try:
                    decrypted_amount_str = self.encryption_service.decrypt(tx.amount)
                    if not decrypted_amount_str:
                        continue
                    parts = decrypted_amount_str.strip().split()
                    amt = float(parts[0]) if parts else 0.0
                    curr = parts[1].upper() if len(parts) > 1 else "USD"
                    
                    if curr == primary_currency.upper():
                        tx_type = getattr(tx, "tx_type", "expense") or "expense"
                        if tx_type == "income":
                            total_in += amt
                        else:
                            total_out += amt
                except Exception as e:
                    logger.warning(f"Failed to decrypt transaction {tx.id} for cash flow snapshot: {e}")
''')
orch_code = orch_code.replace(orig_loop, optimized_loop)

# Fix safe_mirror_to_notion signature
orch_code = orch_code.replace('async def _safe_mirror_to_notion(self, family_id: UUID, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], transaction_id: Optional[UUID] = None):', 'async def _safe_mirror_to_notion(self, family_id: UUID, amount: float, currency: str, concept: str, category: str, timestamp: datetime.datetime, user_name: Optional[str], transaction_id: Optional[UUID] = None, tx_type: str = "expense"):')
orch_code = orch_code.replace('transaction_id=transaction_id', 'transaction_id=transaction_id,\n                    tx_type=tx_type')
orch_code = orch_code.replace('transaction_id=tx_id', 'transaction_id=tx_id,\n                                    tx_type=result.type')

# Fix user_info error handling regression
orch_code = orch_code.replace('user_info = await asyncio.to_thread(self._get_user_info, user_uuid)\n                            family_id = user_info["family_id"]', 'try:\n                                user_info = await asyncio.to_thread(self._get_user_info, user_uuid)\n                                family_id = user_info["family_id"]\n                            except Exception as u_err:\n                                logger.warning(f"Failed to get user info: {u_err}")\n                                family_id = await asyncio.to_thread(self._get_user_family_id, user_uuid)\n                                user_info = {"display_name": "User"}')

# Fix duplicated date_str
orch_code = orch_code.replace('date_str = ""\n                                if result.transaction_date:\n                                    date_str = f" (logged for {transaction_time.strftime(\'%b %d, %Y\')})"','')
# insert it before if result.type == "income":
orch_code = orch_code.replace('if result.type == "income":', 'date_str = ""\n                            if getattr(result, "transaction_date", None):\n                                date_str = f" (logged for {transaction_time.strftime(\'%b %d, %Y\')})"\n                            if result.type == "income":')

# Fix concept or category is None
orch_code = orch_code.replace('if result.concept.strip().lower() == result.category.strip().lower():', 'if (result.concept or "").strip().lower() == (result.category or "").strip().lower():')

orch_path.write_text(orch_code, encoding='utf-8')
print("Patched!")
