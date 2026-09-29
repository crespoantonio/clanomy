import binascii
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from src.core.config import settings

class EncryptionService:
    def __init__(self, key: Optional[str] = None):
        raw_key = key if key is not None else settings.ENCRYPTION_KEY
        try:
            self.fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY format. Must be 32-byte base64. Error: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts a plaintext string and returns a base64-encoded ciphertext string.
        """
        if not isinstance(plaintext, str) or not plaintext:
            return ""
        
        # Fernet encrypt returns bytes, we decode to string for storage
        token = self.fernet.encrypt(plaintext.encode())
        return token.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypts a base64-encoded ciphertext string and returns the plaintext string.
        Handles InvalidToken and ValueError (non-base64) gracefully.
        """
        if not isinstance(ciphertext, str) or not ciphertext:
            return ""
            
        try:
            # Fernet decrypt returns bytes, we decode back to string
            plaintext_bytes = self.fernet.decrypt(ciphertext.encode())
            return plaintext_bytes.decode()
        except (InvalidToken, ValueError, binascii.Error):
            # Graceful return for invalid/corrupted tokens
            return ""

    @staticmethod
    def generate_key() -> str:
        """
        Generates a new valid Fernet key.
        """
        return Fernet.generate_key().decode()
