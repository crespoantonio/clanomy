import pytest
from src.core.encryption import EncryptionService
from cryptography.fernet import Fernet

def test_encryption_roundtrip():
    service = EncryptionService()
    texts = ["Secret Message 123", "$15 Coffee", "Special Characters: ñ, á, 👋"]
    
    for plaintext in texts:
        ciphertext = service.encrypt(plaintext)
        assert ciphertext != plaintext
        assert isinstance(ciphertext, str)
        
        decrypted = service.decrypt(ciphertext)
        assert decrypted == plaintext

def test_encryption_edge_cases():
    service = EncryptionService()
    # Empty string
    assert service.encrypt("") == ""
    assert service.decrypt("") == ""
    # None type
    assert service.encrypt(None) == ""
    assert service.decrypt(None) == ""

def test_encryption_invalid_token():
    service = EncryptionService()
    # A valid base64 string that is NOT a valid Fernet token for this key
    other_key = Fernet.generate_key()
    wrong_token = Fernet(other_key).encrypt(b"wrong key message").decode()
    
    assert service.decrypt(wrong_token) == ""
    assert service.decrypt("not-base64-at-all!") == ""
