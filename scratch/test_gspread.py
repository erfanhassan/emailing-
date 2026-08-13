import os
import json
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)
url = os.environ.get("GOOGLE_SHEET_URL_OR_ID")
print("URL:", url)
sh = gc.open_by_url(url)
print("Sheet title:", sh.title)
