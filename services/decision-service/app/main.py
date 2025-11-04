"""Main entry point for decision-service."""

import asyncio

from shared.core.logging import configure_logging

from app.consumers.decision_consumer import main as consumer_main

# Configure logging at startup
configure_logging()

if __name__ == "__main__":
    """Run the decision service consumer."""
    asyncio.run(consumer_main())
