import os
import sys

print("Checking imports...")
try:
    import app
    print("app.py OK (mostly syntax)")
except Exception as e:
    print(f"app.py error: {e}")

try:
    import background_worker
    print("background_worker.py OK")
except Exception as e:
    print(f"background_worker.py error: {e}")

try:
    import ai_agent
    print("ai_agent.py OK")
except Exception as e:
    print(f"ai_agent.py error: {e}")

try:
    import geo_search
    print("geo_search.py OK")
except Exception as e:
    print(f"geo_search.py error: {e}")

try:
    import email_sender
    print("email_sender.py OK")
except Exception as e:
    print(f"email_sender.py error: {e}")
    
try:
    import scraper
    print("scraper.py OK")
except Exception as e:
    print(f"scraper.py error: {e}")

print("Done.")
