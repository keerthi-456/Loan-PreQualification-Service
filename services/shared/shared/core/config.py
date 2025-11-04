"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Loan Prequalification API"
    app_version: str = "1.0.0"
    environment: str = "local"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/loandb"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600  # 1 hour
    db_echo: bool = False

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group_credit: str = "credit-service-group"
    kafka_consumer_group_decision: str = "decision-service-group"
    kafka_topic_applications_submitted: str = "loan_applications_submitted"
    kafka_topic_applications: str = "loan_applications_submitted"  # Alias for consumers
    kafka_topic_credit_reports: str = "credit_reports_generated"
    kafka_topic_dlq: str = "loan_processing_dlq"
    kafka_producer_acks: str = "all"
    kafka_producer_retries: int = 3
    kafka_compression_type: str = "gzip"

    # CORS
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
