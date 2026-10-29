"""Test-only WSGI app with a fixed Berlin calendar date for mileage browser checks."""
import os
from datetime import date

from wolfs_garage.api import create_app


app = create_app({
    "GARAGE_DB": os.environ["GARAGE_DB"],
    "GARAGE_PUBLIC_ORIGIN": os.environ.get("GARAGE_PUBLIC_ORIGIN", "http://127.0.0.1:18995"),
    "GARAGE_TODAY_PROVIDER": lambda: date(2026, 10, 29),
})
