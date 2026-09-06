import pytest
import os
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from src.services.export_service import ExportService
from src.db.models import Transaction

@pytest.mark.anyio
async def test_export_service_decrypt_failure():
    service = ExportService()

    # Bad encrypted payload that fails decryption
    bad_tx = Transaction(
        id=uuid4(),
        family_id=uuid4(),
        user_id=uuid4(),
        encrypted_amount="not_encrypted",
        encrypted_concept="not_encrypted",
        encrypted_currency="not_encrypted",
        category="Food",
        timestamp=datetime.now(timezone.utc)
    )
    with patch.object(service.encryption_service, "decrypt", side_effect=Exception("Decryption error")):
        res = service._decrypt_transaction(bad_tx)
        assert res is None

@pytest.mark.anyio
async def test_export_data_cleanup_on_exception():
    service = ExportService()

    with patch("src.services.export_service.Session") as mock_sess, \
         patch("src.services.export_service.asyncio.to_thread", side_effect=RuntimeError("Disk write failed")):
        mock_sess.return_value.__enter__.return_value.exec.return_value.all.return_value = []
        with pytest.raises(RuntimeError, match="Disk write failed"):
            await service.export_data(uuid4(), format="csv")

@pytest.mark.anyio
async def test_export_and_send_cleanup_unlink_error():
    service = ExportService()
    mock_ts = MagicMock()
    mock_ts.send_document = AsyncMock()
    service.telegram_service = mock_ts

    with patch.object(service, "export_data", AsyncMock(return_value=("/tmp/fake_export.csv", 5))), \
         patch("os.path.exists", return_value=True), \
         patch("os.unlink", side_effect=OSError("Permission denied")):
        await service.export_and_send(uuid4(), chat_id=123, format="csv")
        assert mock_ts.send_document.call_count == 1
