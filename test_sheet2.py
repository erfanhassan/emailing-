import os
from dotenv import load_dotenv
import gspread

load_dotenv(override=True)
creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
gc = gspread.service_account(filename=creds_file)
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID")
sh = gc.open_by_key(sheet_url_or_id) if "spreadsheets" not in sheet_url_or_id else gc.open_by_url(sheet_url_or_id)

try:
    worksheet = sh.worksheet("Sheet2")
    all_values = worksheet.get_all_values()
    print(f"Total rows in Sheet2: {len(all_values)}")
    for i, row in enumerate(all_values[:10]):
        print(f"Row {i}: {row}")
except Exception as e:
    print(f"Error: {e}")
