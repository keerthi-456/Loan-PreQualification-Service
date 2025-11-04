"""Main entry point for credit-service."""

import asyncio

from shared.core.logging import configure_logging

from app.consumers.credit_consumer import main as consumer_main

# Configure logging at startup
configure_logging()

if __name__ == "__main__":
    """Run the credit service consumer."""
    asyncio.run(consumer_main())
