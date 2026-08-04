import streamlit as st
import gspread
from gspread.utils import rowcol_to_a1
import os
import sys
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import time
from dotenv import load_dotenv, set_key

import importlib
import scraper
import ai_agent
import email_sender
import geo_search

importlib.reload(scraper)
importlib.reload(ai_agent)
importlib.reload(email_sender)
importlib.reload(geo_search)

from scraper import scrape_website_data
from ai_agent import draft_email_with_deepseek, parse_natural_language_command
from email_sender import send_email

load_dotenv()

st.set_page_config(page_title="AI Outreach Dashboard", layout="wide")
st.title("Human-in-the-Loop AI Cold Outreach")

# Custom CSS for premium styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 1rem;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05);
    }
    .metric-val {
        font-size: 2rem;
        font-weight: 800;
        color: #0F172A;
    }
    .metric-lbl {
        font-size: 0.75rem;
        color: #64748B;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.05em;
        margin-top: 0.25rem;
    }
    .control-card {
        background-color: #FFFFFF;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
    }
    .badge {
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    .badge-new {
        background-color: #DBEAFE;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }
    .badge-followup {
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
</style>
""", unsafe_allow_html=True)

with st.expander("⚙️ AI Agent Instructions (Configure your email format here)", expanded=False):
    st.markdown("Use this section to tell the AI how to format your emails. You don't need to change code anymore!")
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.json")
    
    # Load existing
    default_sender = ""
    default_tone = "Professional and concise"
    default_value = "Saving time and reducing manual work through AI."
    default_extra = "Do not use vague automation terms. Be specific."
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                conf = json.load(f)
                default_sender = conf.get("sender_name", default_sender)
                default_tone = conf.get("tone", default_tone)
                default_value = conf.get("value_proposition", default_value)
                default_extra = conf.get("extra_instructions", default_extra)
        except:
            pass

    with st.form("agent_instructions_form"):
        new_sender = st.text_input("Your Name (for the email signature)", value=default_sender, placeholder="e.g. Erfan")
        new_tone = st.text_input("Email Tone", value=default_tone, placeholder="e.g. Friendly, professional, direct")
        new_value = st.text_area("Core Value Proposition", value=default_value, placeholder="What exactly do you want the AI to pitch?")
        new_extra = st.text_area("Extra Rules (Dos & Don'ts)", value=default_extra, placeholder="e.g. Don't mention X. Always include Y.")
        
        if st.form_submit_button("💾 Save AI Instructions", type="primary"):
            new_conf = {
                "sender_name": new_sender,
                "tone": new_tone,
                "value_proposition": new_value,
                "extra_instructions": new_extra
            }
            with open(config_path, "w") as f:
                json.dump(new_conf, f, indent=4)
            st.success("✅ AI Instructions saved! New drafted emails will use these settings.")

def get_gspread_client():
    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_file or not os.path.exists(creds_file):
        return None
    try:
        return gspread.service_account(filename=creds_file)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {e}")
        return None

gc = get_gspread_client()
sheet_url_or_id = os.environ.get("GOOGLE_SHEET_URL_OR_ID", "")

st.sidebar.header("🔗 Google Sheet Connection")
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
new_sheet_url = st.sidebar.text_input("Google Sheet URL", value=sheet_url_or_id)
if new_sheet_url != sheet_url_or_id:
    set_key(env_path, "GOOGLE_SHEET_URL_OR_ID", new_sheet_url)
    os.environ["GOOGLE_SHEET_URL_OR_ID"] = new_sheet_url
    st.sidebar.success("Google Sheet updated! Reloading...")
    time.sleep(1)
    st.rerun()

sheet_url_or_id = new_sheet_url

if not gc or not sheet_url_or_id:
    st.warning("⚠️ Please provide a Google Sheet URL in the sidebar and ensure your Google credentials are valid.")
    st.stop()

@st.cache_data(ttl=10)
def get_sheet_last_update_time(sheet_url_or_id):
    try:
        if "spreadsheets.google.com" in sheet_url_or_id:
            sh = gc.open_by_url(sheet_url_or_id)
        else:
            sh = gc.open_by_key(sheet_url_or_id)
        return getattr(sh, 'lastUpdateTime', str(time.time()))
    except Exception as e:
        return str(time.time())

@st.cache_data
def fetch_leads(sheet_name, last_update_time):
    try:
        if "spreadsheets.google.com" in sheet_url_or_id:
            sh = gc.open_by_url(sheet_url_or_id)
        else:
            sh = gc.open_by_key(sheet_url_or_id)
            
        worksheet = sh.worksheet(sheet_name)
        all_values = worksheet.get_all_values()
        return all_values
    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return []

def clear_cache():
    clear_cache()
    get_sheet_last_update_time.clear()

st.sidebar.divider()
if "draft_limit" not in st.session_state:
    st.session_state.draft_limit = 5
if "daily_limit" not in st.session_state:
    st.session_state.daily_limit = 50
if "send_delay" not in st.session_state:
    st.session_state.send_delay = 15

if "spreadsheets.google.com" in sheet_url_or_id:
    sh = gc.open_by_url(sheet_url_or_id)
else:
    sh = gc.open_by_key(sheet_url_or_id)

st.sidebar.markdown("---")
all_sheets = [ws.title for ws in sh.worksheets()]
selected_sheet = st.sidebar.selectbox("📂 Select Worksheet", all_sheets)
worksheet = sh.worksheet(selected_sheet)

last_update_time = get_sheet_last_update_time(sheet_url_or_id)
all_values = fetch_leads(selected_sheet, last_update_time)

if not all_values:
    st.info("No data found in the Google Sheet. Please add some leads!")
    st.stop()

headers = all_values[0]
headers_lower = [h.lower().strip() for h in headers]

def find_col(possible_names):
    # First, try an exact match
    for i, h in enumerate(headers_lower):
        if h in possible_names:
            return i
            
    # Next, try finding it as a substring, with some exclusions
    for i, h in enumerate(headers_lower):
        for name in possible_names:
            if name == 'status' and 'email' in h:
                continue
            if name == 'name' and ('first' in h or 'last' in h):
                continue
            if name in h:
                return i
    return -1

from datetime import datetime

# Dynamically find column indexes based on keywords
company_idx = find_col(['company', 'organization', 'business', 'name'])
website_idx = find_col(['website', 'url', 'domain', 'link'])
email_idx = find_col(['email', 'contact'])
status_idx = find_col(['outreach status', 'status'])
subject_idx = find_col(['draft subject', 'subject'])
body_idx = find_col(['draft body', 'body'])
last_contacted_idx = find_col(['last contacted date', 'last contacted', 'contact date'])
orig_body_idx = find_col(['original email body'])
thread_idx = find_col(['thread id'])

# Auto-add missing columns to make it schema-agnostic
missing_cols = []
if status_idx == -1: missing_cols.append("Status")
if subject_idx == -1: missing_cols.append("Draft Subject")
if body_idx == -1: missing_cols.append("Draft Body")
if email_idx == -1: missing_cols.append("Email Address")
if last_contacted_idx == -1: missing_cols.append("Last Contacted Date")
if orig_body_idx == -1: missing_cols.append("Original Email Body")
if thread_idx == -1: missing_cols.append("Thread ID")

if missing_cols:
    with st.spinner(f"Configuring your sheet dynamically. Adding missing columns: {', '.join(missing_cols)}..."):
        for col_name in missing_cols:
            headers.append(col_name)
        worksheet.update(values=[headers], range_name='A1')
        clear_cache()
        st.rerun()

# Build dictionary representations for easy access
leads = []
for i, row in enumerate(all_values[1:]): 
    while len(row) < len(headers):
        row.append("")
    lead_dict = {headers[j]: row[j] for j in range(len(headers))}
    lead_dict['_row_idx'] = i + 2 
    leads.append(lead_dict)

def run_drafting_job(limit):
    updates_made = 0
    for lead in leads:
        if updates_made >= limit:
            st.sidebar.warning(f"Reached the maximum of {limit} drafts for this run.")
            break
            
        row_idx = lead['_row_idx']
        status = lead[headers[status_idx]]
        
        if not status or status.lower().strip() == "new":
            website = lead[headers[website_idx]] if website_idx != -1 else ""
            company = lead[headers[company_idx]] if company_idx != -1 else "Unknown"
            current_email = lead[headers[email_idx]] if email_idx != -1 else ""
            
            if not website:
                for val in lead.values():
                    if isinstance(val, str) and (val.startswith('http') or val.startswith('www.')):
                        website = val
                        break
                        
            if not website:
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                worksheet.update_acell(status_cell, "Skipped - No valid website")
                updates_made += 1
                time.sleep(1)
                continue
                
            scraped_text, found_emails = scrape_website_data(website)
            
            if not current_email and not found_emails:
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                worksheet.update_acell(status_cell, "Skipped - No valid email")
                updates_made += 1
                time.sleep(1)
                continue
                
            if not scraped_text:
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                worksheet.update_acell(status_cell, "Skipped - Scraping failed")
                updates_made += 1
                time.sleep(1)
                continue
                
            subject, body = draft_email_with_deepseek(company, scraped_text)
            
            if subject and body:
                if not current_email:
                    best_email = found_emails[0]
                    email_cell = rowcol_to_a1(row_idx, email_idx + 1)
                    worksheet.update_acell(email_cell, best_email)
            
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                
                worksheet.update_acell(status_cell, "Pending Review")
                worksheet.update_acell(subj_cell, subject)
                worksheet.update_acell(body_cell, body)
                
                updates_made += 1
                time.sleep(1)
            else:
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                worksheet.update_acell(status_cell, "Skipped - AI draft failed")
                updates_made += 1
                time.sleep(1)
    return updates_made

def run_followup_job(limit):
    updates_made = 0
    now = datetime.now()
    
    for lead in leads:
        if updates_made >= limit:
            st.sidebar.warning(f"Reached the maximum of {limit} follow-ups for this run.")
            break
            
        row_idx = lead['_row_idx']
        status = lead[headers[status_idx]]
        last_contacted = lead[headers[last_contacted_idx]] if last_contacted_idx != -1 else ""
        
        if status.strip().lower() == "sent" and last_contacted:
            try:
                last_date = datetime.strptime(last_contacted, "%Y-%m-%d")
                days_since = (now - last_date).days
                
                if days_since >= 3:
                    website = lead[headers[website_idx]] if website_idx != -1 else ""
                    company = lead[headers[company_idx]] if company_idx != -1 else "Unknown"
                    
                    if not website:
                        for val in lead.values():
                            if isinstance(val, str) and (val.startswith('http') or val.startswith('www.')):
                                website = val
                                break
                    
                    if website:
                        scraped_text, _ = scrape_website_data(website)
                        if scraped_text:
                            original_body = lead.get(headers[orig_body_idx], "") if orig_body_idx != -1 else ""
                            subject, body = draft_email_with_deepseek(company, scraped_text, is_follow_up=True, original_email_text=original_body)
                            if subject and body:
                                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                                subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                                body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                                
                                worksheet.update_acell(status_cell, "Follow-Up Pending Review")
                                worksheet.update_acell(subj_cell, subject)
                                worksheet.update_acell(body_cell, body)
                                
                                updates_made += 1
                                time.sleep(1)
            except ValueError:
                pass
    return updates_made

def run_sending_job(limit, delay):
    sent_count = 0
    for lead in leads:
        if sent_count >= limit:
            st.sidebar.warning(f"Daily limit of {limit} reached.")
            break
            
        row_idx = lead['_row_idx']
        status = lead[headers[status_idx]]
        
        if status.strip().lower() == "approved":
            to_email = lead[headers[email_idx]]
            subject = lead[headers[subject_idx]]
            body = lead[headers[body_idx]]
            
            if to_email and subject and body:
                thread_id = lead.get(headers[thread_idx], "") if thread_idx != -1 else ""
                success, msg_id = send_email(to_email, subject, body, thread_id=thread_id)
                if success:
                    status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                    worksheet.update_acell(status_cell, "Sent")
                    
                    if thread_idx != -1 and msg_id:
                        worksheet.update_acell(rowcol_to_a1(row_idx, thread_idx + 1), msg_id)
                        
                    if orig_body_idx != -1:
                        worksheet.update_acell(rowcol_to_a1(row_idx, orig_body_idx + 1), body)
                    
                    # Update Last Contacted Date
                    if last_contacted_idx != -1:
                        date_cell = rowcol_to_a1(row_idx, last_contacted_idx + 1)
                        worksheet.update_acell(date_cell, datetime.now().strftime("%Y-%m-%d"))
                        
                    sent_count += 1
                    time.sleep(delay)
                else:
                    st.sidebar.error(f"Failed to send email to {to_email}")
    return sent_count


# Calculate pipeline metrics
total_leads = len(leads)
pending_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "pending review"]
followup_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "follow-up pending review"]
approved_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "approved"]
sent_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "sent"]
new_list = [lead for lead in leads if not lead[headers[status_idx]] or lead[headers[status_idx]].strip().lower() == "new"]

total_pending = len(pending_list)
total_followup = len(followup_list)
total_approved = len(approved_list)
total_sent = len(sent_list)
total_new = len(new_list)

# Render Metrics Panel
st.markdown("### 📊 Outreach Pipeline Overview")
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
with m_col1:
    st.markdown(f'<div class="metric-card"><div class="metric-val">{total_leads}</div><div class="metric-lbl">Total Leads</div></div>', unsafe_allow_html=True)
with m_col2:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color: #3B82F6;">{total_pending + total_followup}</div><div class="metric-lbl">Pending Review 📥</div></div>', unsafe_allow_html=True)
with m_col3:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color: #10B981;">{total_approved}</div><div class="metric-lbl">Ready to Send 📤</div></div>', unsafe_allow_html=True)
with m_col4:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color: #8B5CF6;">{total_sent}</div><div class="metric-lbl">Emails Sent 🚀</div></div>', unsafe_allow_html=True)
with m_col5:
    st.markdown(f'<div class="metric-card"><div class="metric-val" style="color: #64748B;">{total_new}</div><div class="metric-lbl">New Leads 🆕</div></div>', unsafe_allow_html=True)

# Sidebar: Simple Worksheet and URL Manager + Force Sync
st.sidebar.divider()
if st.sidebar.button("🔄 Force Sync with Sheet", use_container_width=True, type="primary"):
    clear_cache()
    st.sidebar.success("Cache cleared! Fetching fresh data...")
    st.rerun()

st.sidebar.metric(label="Total Emails Sent 🚀", value=total_sent)

st.markdown("---")
# Quick Actions and Control Settings
st.markdown("### ⚡ Outreach Command Center")
with st.container(border=True):
    col_act, col_cfg = st.columns([2, 1])
    with col_act:
        st.markdown("**Run Outreach Jobs**")
        st.write("Trigger automated batch processing for email drafting and sending.")
        btn_col1, btn_col2, btn_col3 = st.columns(3)
        with btn_col1:
            if st.button("🔍 Fetch & Draft New Leads", use_container_width=True, type="primary", help="Scrape websites, extract emails, and draft cold pitches for 'New' leads"):
                with st.spinner("Analyzing websites, finding emails, and drafting pitches..."):
                    updates_made = run_drafting_job(st.session_state.draft_limit)
                    if updates_made > 0:
                        st.success(f"Drafted {updates_made} new leads.")
                        clear_cache()
                        st.rerun()
                    else:
                        st.info("No 'New' leads with valid websites found.")
        with btn_col2:
            if st.button("➕ Draft Follow-Ups (3-Day)", use_container_width=True, help="Scan previously contacted leads (3+ days ago) and draft custom follow-up emails"):
                with st.spinner("Scanning for leads contacted 3+ days ago and drafting follow-ups..."):
                    updates_made = run_followup_job(st.session_state.draft_limit)
                    if updates_made > 0:
                        st.success(f"Drafted {updates_made} follow-up emails.")
                        clear_cache()
                        st.rerun()
                    else:
                        st.info("No leads currently qualify for a follow-up.")
        with btn_col3:
            if st.button("🚀 Send Approved Queue", use_container_width=True, type="primary", help="Send all 'Approved' emails via SMTP"):
                with st.spinner("Sending approved emails from queue..."):
                    sent_count = run_sending_job(st.session_state.daily_limit, st.session_state.send_delay)
                    if sent_count > 0:
                        st.success(f"Successfully sent {sent_count} emails.")
                        clear_cache()
                        st.rerun()
                    else:
                        st.info("No 'Approved' emails in queue to send.")
                        
    with col_cfg:
        st.markdown("**Outreach Parameters**")
        st.number_input("Max Drafts per Run", min_value=1, max_value=500, key="draft_limit")
        st.number_input("Max Emails to Send", min_value=1, max_value=500, key="daily_limit")
        st.slider("Delay between emails (sec)", min_value=1, max_value=60, key="send_delay")

with st.expander("🌍 Geo-Targeted Lead Finder (Automated Search)", expanded=True):
    st.markdown("Search for local businesses and automatically add them to your outreach list.")
    col_loc, col_ind = st.columns(2)
    with col_loc:
        search_location = st.text_input("Location", placeholder="e.g., New York, Dhaka")
    with col_ind:
        search_industry = st.text_input("Industry", placeholder="e.g., Salons, Restaurants")
        
    if st.button("🔍 Search Local Businesses", type="primary"):
        if not search_location or not search_industry:
            st.error("Please provide both a location and an industry.")
        else:
            with st.spinner(f"Searching for {search_industry} in {search_location}..."):
                results = geo_search.discover_businesses(search_location, search_industry)
                if not results:
                    st.info(f"No results found for {search_industry} in {search_location}. Have you set your API key in geo_search.py?")
                else:
                    master_sheet_name = "Discovered Leads"
                    clean_headers = ["Company", "Location", "Industry", "Website", "Phone Number", "Email Address", "Status", "Draft Subject", "Draft Body", "Last Contacted Date"]
                    try:
                        new_ws = sh.add_worksheet(title=master_sheet_name, rows="1000", cols="20")
                        new_ws.append_row(clean_headers)
                    except gspread.exceptions.APIError:
                        # Sheet might already exist, get it
                        new_ws = sh.worksheet(master_sheet_name)
                        
                    # Fetch existing websites to prevent duplicates (Column 4 is Website)
                    try:
                        existing_websites = set(new_ws.col_values(4))
                    except Exception:
                        existing_websites = set()
                        
                    added_count = 0
                    for b in results:
                        website = b.get("website", "")
                        # Skip if no website or already in our list
                        if not website or website in existing_websites:
                            continue
                            
                        # Scrape the website to find an email BEFORE adding to sheet
                        scraped_text, found_emails = scrape_website_data(website)
                        
                        # Only add the lead if we successfully found an authentic email
                        if found_emails:
                            new_row = [""] * len(clean_headers)
                            new_row[0] = b.get("name", "")
                            new_row[1] = search_location
                            new_row[2] = search_industry
                            new_row[3] = website
                            new_row[4] = b.get("phone", "")
                            new_row[5] = found_emails[0]
                            new_row[6] = "New"
                            
                            new_ws.append_row(new_row)
                            existing_websites.add(website)
                            added_count += 1
                            time.sleep(0.5) # Avoid rate limits

                    
                    st.success(f"Added {added_count} leads! They were placed in the '{master_sheet_name}' sheet. Please select it from the left sidebar to process them.")
                    clear_cache()
                    time.sleep(2)
                    st.rerun()

with st.expander("💬 Command Center (Talk to your AI)", expanded=False):
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_interactive_draft" not in st.session_state:
        st.session_state.pending_interactive_draft = None

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Command your sales force (e.g., 'draft 5 emails', 'send approved')"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                intent = parse_natural_language_command(prompt)
                action = intent.get("action", "unknown")
                limit = intent.get("limit", 5)

            if action == "draft":
                st.markdown(f"Executing drafting job for up to {limit} leads...")
                updates_made = run_drafting_job(limit)
                if updates_made > 0:
                    response = f"Successfully drafted {updates_made} new leads."
                    st.success(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()
                else:
                    response = "No 'New' leads with valid websites found."
                    st.info(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

            elif action == "send":
                st.markdown(f"Executing sending job for up to {limit} emails...")
                sent_count = run_sending_job(limit, send_delay)
                if sent_count > 0:
                    response = f"Successfully sent {sent_count} emails."
                    st.success(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()
                else:
                    response = "No 'Approved' emails in queue to send."
                    st.info(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

            elif action == "interactive_draft":
                company = intent.get("company", "")
                website = intent.get("website", "")
                if not company:
                    response = "I need a company name to draft an email."
                    st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    st.markdown(f"Scraping {company} and drafting email...")
                    if not website:
                        website = f"www.{company.lower().replace(' ', '')}.com"
                    
                    scraped_text, found_emails = scrape_website_data(website)
                    if scraped_text:
                        subject, body = draft_email_with_deepseek(company, scraped_text)
                        if subject and body:
                            if found_emails:
                                best_email = found_emails[0]
                            else:
                                clean_domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                                best_email = f"info@{clean_domain}" if clean_domain else ""
                                
                            st.session_state.pending_interactive_draft = {
                                "company": company,
                                "website": website,
                                "to_email": best_email,
                                "subject": subject,
                                "body": body
                            }
                            response = f"Drafted email for {company}. See the editor below to review and send."
                            st.success(response)
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            st.rerun()
                        else:
                            response = f"Failed to draft email for {company}."
                            st.error(response)
                            st.session_state.messages.append({"role": "assistant", "content": response})
                    else:
                        response = f"Could not scrape data for {company} at {website}."
                        st.error(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})

            elif action == "delete_by_status":
                status_to_delete = intent.get("status", "")
                if not status_to_delete:
                    response = "I need a status to delete (e.g., 'Rejected')."
                    st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    st.markdown(f"Deleting all leads with status: {status_to_delete}...")
                    deleted_count = 0
                    for lead in reversed(leads):
                        if lead[headers[status_idx]].lower().strip() == status_to_delete.lower().strip():
                            worksheet.delete_rows(lead['_row_idx'])
                            deleted_count += 1
                    response = f"Successfully deleted {deleted_count} leads with status '{status_to_delete}'."
                    st.success(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()

            elif action == "add_lead":
                company = intent.get("company", "")
                website = intent.get("website", "")
                if not company:
                    response = "I need at least a company name to add a lead."
                    st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    if not website:
                        website = f"www.{company.lower().replace(' ', '')}.com"
                        
                    st.markdown(f"Scraping and auto-drafting for {company}...")
                    scraped_text, found_emails = scrape_website_data(website)
                    
                    subject, body = "", ""
                    best_email = ""
                    status = "New"
                    
                    if scraped_text:
                        subject, body = draft_email_with_deepseek(company, scraped_text)
                        if subject and body:
                            if found_emails:
                                best_email = found_emails[0]
                            else:
                                clean_domain = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
                                best_email = f"info@{clean_domain}" if clean_domain else ""
                            status = "Pending Review"

                    new_row = [""] * len(headers)
                    if company_idx != -1: new_row[company_idx] = company
                    if website_idx != -1: new_row[website_idx] = website
                    if email_idx != -1 and best_email: new_row[email_idx] = best_email
                    if subject_idx != -1 and subject: new_row[subject_idx] = subject
                    if body_idx != -1 and body: new_row[body_idx] = body
                    if status_idx != -1: new_row[status_idx] = status
                    
                    worksheet.append_row(new_row)
                    
                    if status == "Pending Review":
                        response = f"Added {company} and successfully auto-drafted an email."
                    else:
                        response = f"Added {company} but failed to auto-draft (could not scrape or draft)."
                        
                    st.success(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()

            elif action == "update_status":
                company = intent.get("company", "")
                new_status = intent.get("status", "")
                if not company or not new_status:
                    response = "I need both a company name and a status to update."
                    st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    updated = False
                    for lead in leads:
                        if company.lower() in lead[headers[company_idx]].lower():
                            cell = rowcol_to_a1(lead['_row_idx'], status_idx + 1)
                            worksheet.update_acell(cell, new_status)
                            updated = True
                            break
                    if updated:
                        response = f"Successfully updated {company}'s status to {new_status}."
                        st.success(response)
                    else:
                        response = f"Could not find a lead matching {company}."
                        st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()

            elif action == "delete_lead":
                company = intent.get("company", "")
                if not company:
                    response = "I need a company name to delete."
                    st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    deleted_count = 0
                    for lead in reversed(leads):
                        if company.lower().strip() == lead[headers[company_idx]].lower().strip():
                            worksheet.delete_rows(lead['_row_idx'])
                            deleted_count += 1
                    if deleted_count > 0:
                        response = f"Successfully deleted {deleted_count} instance(s) of lead: {company}."
                        st.success(response)
                    else:
                        response = f"Could not find an exact match for {company}."
                        st.warning(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    clear_cache()
                    st.rerun()

            elif action == "clear_all":
                if len(all_values) > 1:
                    worksheet.resize(1)
                    response = "Successfully cleared all leads from the sheet."
                else:
                    response = "The sheet is already empty."
                st.success(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                clear_cache()
                st.rerun()

            else:
                response = "I couldn't understand that command. Try 'draft 5 emails', 'add Apple at apple.com', or 'delete rejected leads'."
                st.warning(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# Render Interactive Draft Editor
if st.session_state.get("pending_interactive_draft"):
    draft = st.session_state.pending_interactive_draft
    st.markdown("### 📝 Interactive Email Editor")
    with st.container(border=True):
        st.write(f"**Drafting for:** {draft['company']} ({draft['website']})")
        edited_email = st.text_input("To Email", value=draft["to_email"])
        edited_subject = st.text_input("Subject", value=draft["subject"])
        edited_body = st.text_area("Body", value=draft["body"], height=200)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("🚀 Send Now", use_container_width=True, type="primary"):
                if not edited_email.strip():
                    st.error("Please enter a valid 'To Email' address before sending.")
                else:
                    with st.spinner("Sending..."):
                        success, msg_id = send_email(edited_email, edited_subject, edited_body)
                        if success:
                            new_row = [""] * len(headers)
                            if company_idx != -1: new_row[company_idx] = draft['company']
                            if website_idx != -1: new_row[website_idx] = draft['website']
                            if email_idx != -1: new_row[email_idx] = edited_email
                            if subject_idx != -1: new_row[subject_idx] = edited_subject
                            if body_idx != -1: new_row[body_idx] = edited_body
                            if status_idx != -1: new_row[status_idx] = "Sent"
                            if thread_idx != -1 and msg_id: new_row[thread_idx] = msg_id
                            if orig_body_idx != -1: new_row[orig_body_idx] = edited_body
                            
                            worksheet.append_row(new_row)
                            st.success(f"Successfully sent email to {edited_email}!")
                            st.session_state.messages.append({"role": "assistant", "content": f"✅ Sent email to {draft['company']} at {edited_email}."})
                            st.session_state.pending_interactive_draft = None
                            clear_cache()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to send email. Check your SMTP settings.")
        with col2:
            if st.button("💾 Save Draft", use_container_width=True):
                new_row = [""] * len(headers)
                if company_idx != -1: new_row[company_idx] = draft['company']
                if website_idx != -1: new_row[website_idx] = draft['website']
                if email_idx != -1: new_row[email_idx] = edited_email
                if subject_idx != -1: new_row[subject_idx] = edited_subject
                if body_idx != -1: new_row[body_idx] = edited_body
                if status_idx != -1: new_row[status_idx] = "Pending Review"
                
                worksheet.append_row(new_row)
                st.success(f"Saved draft for {draft['company']} to Pending Review!")
                st.session_state.messages.append({"role": "assistant", "content": f"💾 Saved draft for {draft['company']} to Pending Review queue."})
                st.session_state.pending_interactive_draft = None
                clear_cache()
                time.sleep(1)
                st.rerun()
        with col3:
            if st.button("❌ Discard", use_container_width=True):
                st.session_state.pending_interactive_draft = None
                st.session_state.messages.append({"role": "assistant", "content": f"Discarded draft for {draft['company']}."})
                st.rerun()

st.divider()

tab_pending, tab_approved, tab_sent = st.tabs([f"📥 Pending Review ({total_pending + total_followup})", f"📤 Ready to Send ({total_approved})", f"📨 Previously Sent ({total_sent})"])

with tab_pending:
    pending_leads = [lead for lead in leads if lead[headers[status_idx]].strip().lower() in ["pending review", "follow-up pending review"]]
    if st.session_state.get("draft_limit"):
        pending_leads = pending_leads[:st.session_state.draft_limit]

    if not pending_leads:
        new_leads_count = sum(1 for lead in leads if not lead[headers[status_idx]] or lead[headers[status_idx]].strip().lower() == "new")
        if new_leads_count > 0:
            st.info(f"You have {new_leads_count} new lead(s) waiting to be drafted! Click **'Fetch & Draft (New Leads)'** in the sidebar or use the Command Center to process them.")
        else:
            st.write("No leads are currently pending review.")
    else:
        def toggle_all_pending():
            val = st.session_state.select_all_pending
            for lead in pending_leads:
                st.session_state[f"sel_app_{lead['_row_idx']}"] = val

        bulk_col1, bulk_col2 = st.columns([1, 4])
        with bulk_col1:
            st.checkbox("Select All Pending", key="select_all_pending", on_change=toggle_all_pending)
        with bulk_col2:
            if st.button("✅ Bulk Approve Selected", type="primary"):
                selected_leads = [lead for lead in pending_leads if st.session_state.get(f"sel_app_{lead['_row_idx']}")]
                if not selected_leads:
                    st.warning("No leads selected for bulk approval.")
                else:
                    with st.spinner(f"Approving {len(selected_leads)} leads..."):
                        update_data = []
                        for lead in selected_leads:
                            row_idx = lead['_row_idx']
                            edited_subject = st.session_state.get(f"subj_{row_idx}", lead[headers[subject_idx]])
                            edited_body = st.session_state.get(f"body_{row_idx}", lead[headers[body_idx]])
                            
                            status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                            subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                            body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                            
                            update_data.extend([
                                {'range': subj_cell, 'values': [[edited_subject]]},
                                {'range': body_cell, 'values': [[edited_body]]},
                                {'range': status_cell, 'values': [["Approved"]]}
                            ])
                        
                        if update_data:
                            try:
                                worksheet.batch_update(update_data)
                                st.success(f"Successfully approved {len(selected_leads)} leads!")
                                clear_cache()
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error during bulk update: {e}")

        for lead in pending_leads:
            row_idx = lead['_row_idx']
            company = lead[headers[company_idx]] if company_idx != -1 else "Unknown"
            email_addr = lead[headers[email_idx]] if email_idx != -1 else "No Email"
            website = lead[headers[website_idx]] if website_idx != -1 else ""
            
            col_cb, col_exp = st.columns([0.5, 9.5])
            with col_cb:
                st.write("")
                st.write("")
                st.checkbox("Select", key=f"sel_app_{row_idx}", label_visibility="collapsed")
                
            with col_exp:
                is_followup = lead[headers[status_idx]].strip().lower() == "follow-up pending review"
                badge_html = '<span class="badge badge-followup">⚠️ Follow-Up Pitch</span>' if is_followup else '<span class="badge badge-new">🆕 New Pitch</span>'
                st.markdown(badge_html, unsafe_allow_html=True)
                with st.expander(f"{company} | {email_addr}", expanded=True):
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.markdown("**Company Details**")
                        if website:
                            st.write(f"**Website:** [{website}]({website})")
                        else:
                            st.write("**Website:** Not Found")
                        
                        st.markdown("**Edit Subject:**")
                        edited_subject = st.text_input(
                            "Subject", 
                            value=lead[headers[subject_idx]], 
                            key=f"subj_{row_idx}",
                            label_visibility="collapsed"
                        )
                        
                    with col2:
                        st.markdown("**Edit Email Body:**")
                        edited_body = st.text_area(
                            "Body", 
                            value=lead[headers[body_idx]], 
                            height=200, 
                            key=f"body_{row_idx}",
                            label_visibility="collapsed"
                        )
                        
                    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 8])
                    with btn_col1:
                        if st.button("✅ Approve", key=f"approve_{row_idx}"):
                            status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                            subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                            body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                            
                            worksheet.update_acell(subj_cell, edited_subject)
                            worksheet.update_acell(body_cell, edited_body)
                            worksheet.update_acell(status_cell, "Approved")
                            
                            st.success("Lead approved!")
                            clear_cache()
                            st.rerun()
                    with btn_col2:
                        if st.button("❌ Reject", key=f"reject_{row_idx}"):
                            status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                            worksheet.update_acell(status_cell, "Rejected")
                            st.error("Lead rejected!")
                            clear_cache()
                            st.rerun()

with tab_approved:
    approved_leads = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "approved"]

    if not approved_leads:
        st.write("No approved leads waiting to be sent.")
    else:
        def toggle_all_send():
            val = st.session_state.select_all_send
            for lead in approved_leads:
                st.session_state[f"sel_send_{lead['_row_idx']}"] = val

        bulk_send_col1, bulk_send_col2 = st.columns([1, 4])
        with bulk_send_col1:
            st.checkbox("Select All Approved", key="select_all_send", on_change=toggle_all_send)
        with bulk_send_col2:
            if st.button("🚀 Bulk Send Selected", type="primary"):
                selected_send_leads = [lead for lead in approved_leads if st.session_state.get(f"sel_send_{lead['_row_idx']}")]
                if not selected_send_leads:
                    st.warning("No leads selected for bulk sending.")
                else:
                    with st.spinner(f"Sending {len(selected_send_leads)} emails..."):
                        sent_count = 0
                        update_data = []
                        for lead in selected_send_leads:
                            row_idx = lead['_row_idx']
                            to_email = lead[headers[email_idx]]
                            subject = lead[headers[subject_idx]]
                            body = lead[headers[body_idx]]
                            
                            if to_email and subject and body:
                                thread_id = lead.get(headers[thread_idx], "") if thread_idx != -1 else ""
                                success, msg_id = send_email(to_email, subject, body, thread_id=thread_id)
                                if success:
                                    status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                                    update_data.append({'range': status_cell, 'values': [["Sent"]]})
                                    if thread_idx != -1 and msg_id:
                                        update_data.append({'range': rowcol_to_a1(row_idx, thread_idx + 1), 'values': [[msg_id]]})
                                    if orig_body_idx != -1:
                                        update_data.append({'range': rowcol_to_a1(row_idx, orig_body_idx + 1), 'values': [[body]]})
                                    sent_count += 1
                                    time.sleep(st.session_state.send_delay)
                                else:
                                    st.error(f"Failed to send email to {to_email}")
                        
                        if update_data:
                            try:
                                worksheet.batch_update(update_data)
                            except Exception as e:
                                st.error(f"Error updating sheet: {e}")
                                
                        st.success(f"Successfully sent {sent_count} emails!")
                        clear_cache()
                        time.sleep(1)
                        st.rerun()

        for lead in approved_leads:
            row_idx = lead['_row_idx']
            company = lead[headers[company_idx]] if company_idx != -1 else "Unknown"
            email_addr = lead[headers[email_idx]] if email_idx != -1 else "No Email"
            
            col_cb, col_exp = st.columns([0.5, 9.5])
            with col_cb:
                st.write("")
                st.write("")
                st.checkbox("Select", key=f"sel_send_{row_idx}", label_visibility="collapsed")
                
            with col_exp:
                with st.expander(f"Ready: {company} | {email_addr}", expanded=False):
                    st.write(f"**To:** {email_addr}")
                    st.write(f"**Subject:** {lead[headers[subject_idx]]}")
                    st.text_area("Body", value=lead[headers[body_idx]], height=150, disabled=True, key=f"send_body_{row_idx}")
                    
                    if st.button("🚀 Send Individually", key=f"send_indiv_{row_idx}"):
                        with st.spinner("Sending..."):
                            thread_id = lead.get(headers[thread_idx], "") if thread_idx != -1 else ""
                            success, msg_id = send_email(email_addr, lead[headers[subject_idx]], lead[headers[body_idx]], thread_id=thread_id)
                            if success:
                                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                                worksheet.update_acell(status_cell, "Sent")
                                if thread_idx != -1 and msg_id:
                                    worksheet.update_acell(rowcol_to_a1(row_idx, thread_idx + 1), msg_id)
                                if orig_body_idx != -1:
                                    worksheet.update_acell(rowcol_to_a1(row_idx, orig_body_idx + 1), lead[headers[body_idx]])
                                st.success("Email sent!")
                                clear_cache()
                                st.rerun()
                            else:
                                st.error("Failed to send email.")

with tab_sent:
    sent_leads = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "sent"]

    if not sent_leads:
        st.write("No previously sent emails.")
    else:
        for lead in sent_leads:
            row_idx = lead['_row_idx']
            company = lead[headers[company_idx]] if company_idx != -1 else "Unknown"
            email_addr = lead[headers[email_idx]] if email_idx != -1 else "No Email"
            website = lead[headers[website_idx]] if website_idx != -1 else ""
            
            with st.expander(f"Sent: {company} | {email_addr}", expanded=False):
                st.write(f"**To:** {email_addr}")
                st.write(f"**Subject:** {lead[headers[subject_idx]]}")
                st.text_area("Body", value=lead[headers[body_idx]], height=150, disabled=True, key=f"sent_body_{row_idx}")
                
                if st.button("➕ Draft Follow-up", key=f"followup_{row_idx}"):
                    with st.spinner(f"Scraping {company} and drafting follow-up..."):
                        scraped_text = ""
                        if website:
                            scraped_text, _ = scrape_website_data(website)
                        
                        new_subject = f"Re: {lead[headers[subject_idx]]}"
                        new_body = ""
                        
                        if scraped_text:
                            followup_subj, followup_body = draft_email_with_deepseek(company, scraped_text, is_follow_up=True)
                            if followup_subj and followup_body:
                                new_subject = followup_subj
                                new_body = followup_body
                        
                        new_row = [""] * len(headers)
                        if company_idx != -1: new_row[company_idx] = company
                        if website_idx != -1: new_row[website_idx] = website
                        if email_idx != -1: new_row[email_idx] = email_addr
                        if subject_idx != -1: new_row[subject_idx] = new_subject
                        if body_idx != -1: new_row[body_idx] = new_body
                        if status_idx != -1: new_row[status_idx] = "Pending Review"
                        
                        try:
                            worksheet.append_row(new_row)
                            st.success(f"Follow-up for {company} drafted and added to Pending Review!")
                            clear_cache()
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error adding follow-up row: {e}")

