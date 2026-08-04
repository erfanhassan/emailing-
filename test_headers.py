import os
from dotenv import load_dotenv
import gspread

load_dotenv(override=True)
creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
gc = gspread.service_account(filename=creds_file)
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID")
sh = gc.open_by_key(sheet_url_or_id) if "spreadsheets" not in sheet_url_or_id else gc.open_by_url(sheet_url_or_id)
worksheet = sh.sheet1
headers = worksheet.row_values(1)
print(f"Total headers: {len(headers)}")
for i, h in enumerate(headers):
    if h:
        print(f"Index {i}: '{h}'")
