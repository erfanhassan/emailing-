import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import gspread

creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
gc = gspread.service_account(filename=creds_file)
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID")

sh = gc.open_by_url(sheet_url_or_id)
ws = sh.sheet1
headers = ws.row_values(1)
print(f"Headers: {headers}")
