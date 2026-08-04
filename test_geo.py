import os
from dotenv import load_dotenv
import geo_search

load_dotenv(override=True)
results = geo_search.discover_businesses("Dhaka", "Restaurants")
print(f"Total returned by geo_search: {len(results)}")
for r in results:
    print(r)
