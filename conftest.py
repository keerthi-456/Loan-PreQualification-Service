"""Root conftest.py for pytest configuration."""

import sys
from pathlib import Path

# Add all service paths to sys.path for imports
project_root = Path(__file__).parent
services_root = project_root / "services"

# Add each service and shared library to Python path
sys.path.insert(0, str(services_root / "shared"))
sys.path.insert(0, str(services_root / "prequal-api"))
sys.path.insert(0, str(services_root / "credit-service"))
sys.path.insert(0, str(services_root / "decision-service"))
