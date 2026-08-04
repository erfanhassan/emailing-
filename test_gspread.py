import gspread
import os
from dotenv import load_dotenv

load_dotenv()
creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
gc = gspread.service_account(filename=creds_file)
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID")
sh = gc.open_by_key(sheet_url_or_id) if "http" not in sheet_url_or_id else gc.open_by_url(sheet_url_or_id)
sh.sheet1.update_acell('A1', 'Email Address')
print("Success!")
