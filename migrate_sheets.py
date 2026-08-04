import os
import gspread
import gspread.utils
from dotenv import load_dotenv

load_dotenv()

def migrate():
    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID")
    
    if not creds_file or not sheet_url_or_id:
        print("Missing credentials or sheet ID.")
        return
        
    gc = gspread.service_account(filename=creds_file)
    
    if "docs.google.com" in sheet_url_or_id:
        sh = gc.open_by_url(sheet_url_or_id)
    else:
        sh = gc.open_by_key(sheet_url_or_id)
        
    for ws in sh.worksheets():
        print(f"Migrating worksheet: {ws.title}")
        headers = ws.row_values(1)
        
        if not headers:
            continue
            
        # Add new columns if missing
        if "Original Email Body" not in headers:
            headers.append("Original Email Body")
        if "Thread ID" not in headers:
            headers.append("Thread ID")
            
        ws.update(values=[headers], range_name="A1")
        
        # Get indices
        try:
            status_idx = headers.index("Status")
            subject_idx = headers.index("Draft Subject")
            body_idx = headers.index("Draft Body")
            last_contacted_idx = headers.index("Last Contacted Date")
            orig_body_idx = headers.index("Original Email Body")
            thread_idx = headers.index("Thread ID")
        except ValueError as e:
            print(f"Skipping {ws.title} - missing standard headers: {e}")
            continue
            
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            continue
            
        updates = []
        for row_idx, row in enumerate(all_values[1:], start=2):
            # Extend row if it's shorter than headers
            while len(row) < len(headers):
                row.append("")
                
            # Reset the values
            row[status_idx] = "New"
            row[subject_idx] = ""
            row[body_idx] = ""
            row[last_contacted_idx] = ""
            row[orig_body_idx] = ""
            row[thread_idx] = ""
            
            updates.append(row)
            
        # Bulk update to avoid rate limits
        end_col = gspread.utils.rowcol_to_a1(1, len(headers))
        end_col_letter = end_col.replace('1', '')
        range_name = f"A2:{end_col_letter}{len(updates) + 1}"
        
        ws.update(values=updates, range_name=range_name)
        print(f"Successfully migrated {len(updates)} rows in '{ws.title}'.")
        
if __name__ == "__main__":
    migrate()
