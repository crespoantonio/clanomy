from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices, field_validator
from typing import Optional

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "Clanomy"
    DEFAULT_CURRENCY: str = "USD"
    DEFAULT_TIMEZONE: str = "America/Argentina/Buenos_Aires"
    
    # Database
    DATABASE_URL: str
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    
    # Security
    ENCRYPTION_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: Optional[str] = None
    MESSAGING_WEBHOOK_SECRET: str
    CLOUDFLARE_ORIGIN_SECRET: Optional[str] = None  # Optional secret header token to block direct origin access
    ENABLE_DOCS: bool = False  # Set to True to expose Swagger/OpenAPI docs (/docs, /redoc, /openapi.json)
    USER_COOLDOWN_SECONDS: float = 0.5
    ALLOWED_TELEGRAM_USERS: str = ""  # Comma-separated list of allowed Telegram usernames or IDs (empty = open to all)
    MAX_VOICE_DURATION_SECONDS: int = 60  # Maximum allowable voice note duration in seconds before fast-fail rejection
    MAX_TEXT_LENGTH: int = 350  # Maximum allowable text message length in characters before fast-fail rejection
    FAMILY_INVITE_TTL_HOURS: int = 1  # Family invite link expiration window in hours

    # Monetization & Subscription Settings (Lemon Squeezy Merchant of Record)
    ENABLE_SUBSCRIPTIONS: bool = False
    LEMON_SQUEEZY_API_KEY: Optional[str] = None
    LEMON_SQUEEZY_STORE_ID: Optional[str] = None
    LEMON_SQUEEZY_WEBHOOK_SECRET: Optional[str] = None
    LEMON_SQUEEZY_SOLO_PRO_VARIANT_ID: Optional[str] = None
    LEMON_SQUEEZY_FAMILY_PRO_VARIANT_ID: Optional[str] = None
    LEMON_SQUEEZY_SOLO_PRO_ANNUAL_VARIANT_ID: Optional[str] = None
    LEMON_SQUEEZY_FAMILY_PRO_ANNUAL_VARIANT_ID: Optional[str] = None
    
    # Whisper settings
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 5
    WHISPER_TEMPERATURE: float = 0.0
    WHISPER_VAD_FILTER: bool = False
    WHISPER_MAX_CONCURRENT: int = 1
    
    # AI Engine Configuration (Unified Provider / OpenAI-Compatible Standard)
    AI_PROVIDER: Optional[str] = None
    AI_API_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")
    )
    AI_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        validation_alias=AliasChoices("AI_BASE_URL", "AI_API_BASE_URL", "GROQ_BASE_URL")
    )
    AI_MODEL: str = "llama-3.3-70b-versatile"
    AI_WHISPER_MODEL: str = "whisper-large-v3-turbo"
    AI_MAX_RETRIES: int = 3
    AI_RETRY_BACKOFF_MIN: float = 0.5
    AI_RETRY_BACKOFF_MAX: float = 4.0

    # Local Ollama Fallback (Used when AI_API_KEY is empty / self-hosting)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_MAX_CONCURRENT: int = 2
    MAX_QUERY_TRANSACTIONS_LIMIT: int = 500

    # HTTP Client Pool Settings
    HTTP_POOL_MAX_CONNECTIONS: int = 50
    HTTP_POOL_MAX_KEEPALIVE: int = 20
    HTTP_TIMEOUT: float = 30.0
    
    # Database URL Normalization (Render / SQLAlchemy 2 with psycopg3)
    @field_validator("DATABASE_URL", mode="before")
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+psycopg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+psycopg://"):
                return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    # Callback (Removed n8n)    
    @field_validator("WHISPER_DEVICE")
    def validate_whisper_device(cls, v: str) -> str:
        allowed = {"cpu", "cuda", "auto"}
        if v.lower() not in allowed:
            raise ValueError(f"WHISPER_DEVICE must be one of {allowed}")
        return v.lower()

    @field_validator("WHISPER_COMPUTE_TYPE")
    def validate_whisper_compute_type(cls, v: str) -> str:
        allowed = {"int8", "int8_float16", "int16", "float16", "float32", "default"}
        if v.lower() not in allowed:
            raise ValueError(f"WHISPER_COMPUTE_TYPE must be one of {allowed}")
        return v.lower()
        
    @field_validator("OLLAMA_BASE_URL")
    def validate_ollama_base_url(cls, v: str) -> str:
        from urllib.parse import urlparse
        if not v.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must start with http:// or https://")
        parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError("OLLAMA_BASE_URL must contain a valid host (e.g. localhost or domain)")
        return v

    @field_validator("OLLAMA_MODEL")
    def validate_ollama_model(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("OLLAMA_MODEL cannot be empty")
        return v.strip()

    @field_validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ENCRYPTION_KEY cannot be empty")
        from cryptography.fernet import Fernet
        try:
            Fernet(v.strip().encode())
        except Exception as e:
            raise ValueError(f"ENCRYPTION_KEY must be a valid 32-byte URL-safe base64 Fernet key. Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\". Error: {e}")
        return v.strip()

    # Configuration
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
