import os
from dotenv import load_dotenv
import geo_search

load_dotenv(override=True)
results = geo_search.discover_businesses("Dhaka", "Restaurants")
print(f"Results found: {len(results)}")
print(results)
