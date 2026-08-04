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
import email_verifier
import plotly.express as px
import pandas as pd

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

def render_campaigns():
    st.markdown("Create multiple AI campaigns. The AI will randomly select one to test which messaging performs better.")
    
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.json")
    
    campaigns = {"Default": {
        "sender_name": "", "tone": "Professional and concise", 
        "value_proposition": "Saving time and reducing manual work through AI.", 
        "extra_instructions": "Do not use vague automation terms."
    }}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                conf = json.load(f)
                if isinstance(conf, dict) and any(isinstance(v, dict) for v in conf.values()):
                    campaigns = conf
                else:
                    campaigns["Default"] = conf
        except:
            pass

    camp_tabs = st.tabs(list(campaigns.keys()) + ["+ New Campaign"])
    
    for i, (camp_name, camp_data) in enumerate(campaigns.items()):
        with camp_tabs[i]:
            with st.form(f"agent_instructions_form_{i}"):
                new_sender = st.text_input("Your Name (for the email signature)", value=camp_data.get("sender_name", ""), placeholder="e.g. Erfan")
                new_tone = st.text_input("Email Tone", value=camp_data.get("tone", ""), placeholder="e.g. Friendly, professional, direct")
                new_value = st.text_area("Core Value Proposition", value=camp_data.get("value_proposition", ""), placeholder="What exactly do you want the AI to pitch?")
                new_extra = st.text_area("Extra Rules (Dos & Don'ts)", value=camp_data.get("extra_instructions", ""), placeholder="e.g. Don't mention X.")
                
                if st.form_submit_button(f"💾 Save {camp_name} Campaign", type="primary"):
                    campaigns[camp_name] = {
                        "sender_name": new_sender, "tone": new_tone,
                        "value_proposition": new_value, "extra_instructions": new_extra
                    }
                    with open(config_path, "w") as f:
                        json.dump(campaigns, f, indent=4)
                    st.success(f"✅ {camp_name} Campaign saved!")
                    
    with camp_tabs[-1]:
        with st.form("new_campaign_form"):
            new_camp_name = st.text_input("New Campaign Name", placeholder="e.g. Aggressive Pitch")
            if st.form_submit_button("➕ Create Campaign"):
                if new_camp_name and new_camp_name not in campaigns:
                    campaigns[new_camp_name] = campaigns["Default"].copy()
                    with open(config_path, "w") as f:
                        json.dump(campaigns, f, indent=4)
                    st.success("Campaign created! Reloading...")
                    st.rerun()

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
    st.cache_data.clear()

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
campaign_idx = find_col(['campaign'])

# Auto-add missing columns to make it schema-agnostic
missing_cols = []
if status_idx == -1: missing_cols.append("Status")
if subject_idx == -1: missing_cols.append("Draft Subject")
if body_idx == -1: missing_cols.append("Draft Body")
if email_idx == -1: missing_cols.append("Email Address")
if campaign_idx == -1: missing_cols.append("Campaign")
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
                
            subject, body, campaign_used = draft_email_with_deepseek(company, scraped_text)
            
            if subject and body:
                target_email = current_email
                if not target_email:
                    target_email = found_emails[0]
                    
                # Verify email
                if not email_verifier.verify_email(target_email):
                    status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                    worksheet.update_acell(status_cell, "Skipped - Invalid Email")
                    updates_made += 1
                    time.sleep(1)
                    continue

                if not current_email:
                    email_cell = rowcol_to_a1(row_idx, email_idx + 1)
                    worksheet.update_acell(email_cell, target_email)
            
                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                
                worksheet.update_acell(status_cell, "Pending Review")
                worksheet.update_acell(subj_cell, subject)
                worksheet.update_acell(body_cell, body)
                if campaign_idx != -1:
                    camp_cell = rowcol_to_a1(row_idx, campaign_idx + 1)
                    worksheet.update_acell(camp_cell, campaign_used)
                
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
                            subject, body, campaign_used = draft_email_with_deepseek(company, scraped_text, is_follow_up=True, original_email_text=original_body)
                            if subject and body:
                                status_cell = rowcol_to_a1(row_idx, status_idx + 1)
                                subj_cell = rowcol_to_a1(row_idx, subject_idx + 1)
                                body_cell = rowcol_to_a1(row_idx, body_idx + 1)
                                
                                worksheet.update_acell(status_cell, "Follow-Up Pending Review")
                                worksheet.update_acell(subj_cell, subject)
                                worksheet.update_acell(body_cell, body)
                                if campaign_idx != -1:
                                    camp_cell = rowcol_to_a1(row_idx, campaign_idx + 1)
                                    worksheet.update_acell(camp_cell, campaign_used)
                                
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
opened_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "opened"]
clicked_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "clicked"]
replied_list = [lead for lead in leads if lead[headers[status_idx]].strip().lower() == "replied"]
new_list = [lead for lead in leads if not lead[headers[status_idx]] or lead[headers[status_idx]].strip().lower() == "new"]

total_pending = len(pending_list)
total_followup = len(followup_list)
total_approved = len(approved_list)
total_sent = len(sent_list) + len(opened_list) + len(clicked_list) + len(replied_list)
total_opened = len(opened_list) + len(clicked_list) + len(replied_list)
total_clicked = len(clicked_list) + len(replied_list)
total_replied = len(replied_list)
total_new = len(new_list)

# Render Metrics Panel
def render_dashboard():
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
        st.markdown(f'<div class="metric-card"><div class="metric-val" style="color: #F59E0B;">{total_replied}</div><div class="metric-lbl">Replies 💬</div></div>', unsafe_allow_html=True)

    st.markdown("### 📈 Conversion Funnel")
    funnel_data = dict(
        number=[total_leads, total_sent, total_opened, total_clicked, total_replied],
        stage=["Total Leads", "Sent", "Opened", "Clicked", "Replied"]
    )
    fig = px.funnel(funnel_data, x='number', y='stage')
    st.plotly_chart(fig, use_container_width=True)

# Sidebar: Simple Worksheet and URL Manager + Force Sync
st.sidebar.divider()
if st.sidebar.button("🔄 Force Sync with Sheet", use_container_width=True, type="primary"):
    clear_cache()
    st.sidebar.success("Cache cleared! Fetching fresh data...")
    st.rerun()

st.sidebar.metric(label="Total Emails Sent 🚀", value=total_sent)

st.sidebar.markdown("---")

# Quick Actions and Control Settings
def render_command_center():
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

    from urllib.parse import urlparse

    def normalize_domain(url: str) -> str:
        if not url:
            return ""
        if not url.startswith("http"):
            url = "http://" + url
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc
        except:
            return url.lower()

    # Initialize state variables for incremental radius grid search
    if "geo_query" not in st.session_state:
        st.session_state.geo_query = ""
    if "geo_sub_locations_pool" not in st.session_state:
        st.session_state.geo_sub_locations_pool = []
    if "geo_sub_locations_searched" not in st.session_state:
        st.session_state.geo_sub_locations_searched = []

def render_geo_sourcing():
        st.markdown("Search for local businesses across neighborhoods and automatically enrich/add them to your outreach list.")
        col_loc, col_ind = st.columns(2)
        with col_loc:
            search_location = st.text_input("Location", placeholder="e.g., New York, Dhaka", key="geo_loc_input")
        with col_ind:
            search_industry = st.text_input("Industry", placeholder="e.g., Salons, Restaurants", key="geo_ind_input")
        
        # Determine dynamic button label for incremental search
        button_label = "🔍 Search Local Businesses"
        current_search = (search_location.strip() + ":" + search_industry.strip()) if search_location and search_industry else ""
        if current_search and st.session_state.geo_query == current_search and st.session_state.geo_sub_locations_searched:
            button_label = f"🔍 Search Again (Next Radius Neighborhoods: {len(st.session_state.geo_sub_locations_searched)} searched)"

        if st.button(button_label, type="primary"):
            if not search_location or not search_industry:
                st.error("Please provide both a location and an industry.")
            else:
                # Set or check query state
                if st.session_state.geo_query != current_search:
                    st.session_state.geo_query = current_search
                    st.session_state.geo_sub_locations_pool = []
                    st.session_state.geo_sub_locations_searched = []
                
                pool = st.session_state.geo_sub_locations_pool
                searched = st.session_state.geo_sub_locations_searched
            
                # Step 1: Sub-Locations pool generation
                if not pool or len(set(pool) - set(searched)) < 3:
                    with st.spinner("Dynamically generating commercial sub-locations for radius grid search..."):
                        new_locs = geo_search.get_sub_locations(search_location, exclude_list=searched)
                        st.session_state.geo_sub_locations_pool = list(set(pool + new_locs))
                        pool = st.session_state.geo_sub_locations_pool
                    
                # Select up to 4 new neighborhoods to search
                remaining = [item for item in pool if item not in searched]
                sub_locs_to_search = remaining[:4]
                if not sub_locs_to_search:
                    sub_locs_to_search = [search_location]
                
                # Stage 1: Discovery (Raw business yield)
                status_placeholder = st.empty()
                progress_bar = st.progress(0.0)
            
                status_placeholder.info(f"🔎 Starting Stage 1 (Discovery) across: {', '.join(sub_locs_to_search)}...")
                time.sleep(1)
            
                raw_results = []
                for idx, sub_loc in enumerate(sub_locs_to_search):
                    status_placeholder.markdown(f"🔎 **Stage 1 (Discovery)**: Searching `{search_industry}` in `{sub_loc}` ({idx+1}/{len(sub_locs_to_search)})...")
                    progress_bar.progress((idx) / len(sub_locs_to_search))
                
                    batch = geo_search.discover_businesses(sub_loc, search_industry)
                    raw_results.extend(batch)
                    time.sleep(0.5)
                
                progress_bar.progress(1.0)
            
                # Retrieve existing website domains from sheet for deduplication
                master_sheet_name = "Discovered Leads"
                clean_headers = ["Company", "Location", "Industry", "Website", "Phone Number", "Email Address", "Status", "Draft Subject", "Draft Body", "Last Contacted Date"]
                try:
                    new_ws = sh.add_worksheet(title=master_sheet_name, rows="1000", cols="20")
                    new_ws.append_row(clean_headers)
                except gspread.exceptions.APIError:
                    new_ws = sh.worksheet(master_sheet_name)
                
                try:
                    # Column 4 is Website
                    existing_websites = new_ws.col_values(4)
                    existing_domains = {normalize_domain(url) for url in existing_websites if url}
                except Exception:
                    existing_domains = set()
                
                # Deduplicate the batch
                unique_discovered = []
                seen_domains_this_run = set()
                for b in raw_results:
                    website = b.get("website", "")
                    if not website:
                        continue
                    domain = normalize_domain(website)
                    if domain in existing_domains or domain in seen_domains_this_run:
                        continue
                    unique_discovered.append(b)
                    seen_domains_this_run.add(domain)
                
                # Stage 2: Email Scraping & Enrichment
                total_to_process = len(unique_discovered)
                if total_to_process == 0:
                    status_placeholder.warning("No new unique businesses discovered in this batch. Try searching again for adjacent areas.")
                    st.session_state.geo_sub_locations_searched = list(set(searched + sub_locs_to_search))
                else:
                    status_placeholder.success(f"Discovered **{total_to_process}** unique businesses. Starting Stage 2 (Email Scraping)...")
                    progress_bar.progress(0.0)
                
                    added_count = 0
                    skipped_count = 0
                
                    for idx, b in enumerate(unique_discovered):
                        status_placeholder.markdown(f"⚡ **Stage 2 (Scraping)**: Scraping emails ({idx+1}/{total_to_process}) for **{b['name']}**...")
                        progress_bar.progress((idx) / total_to_process)
                    
                        website = b.get("website")
                        scraped_text, found_emails = scrape_website_data(website)
                    
                        if found_emails:
                            # Append the lead to sheet
                            new_row = [""] * len(clean_headers)
                            new_row[0] = b.get("name", "")
                            new_row[1] = b.get("address") or search_location
                            new_row[2] = search_industry
                            new_row[3] = website
                            new_row[4] = b.get("phone", "")
                            new_row[5] = found_emails[0]
                            new_row[6] = "New"
                        
                            new_ws.append_row(new_row)
                            added_count += 1
                            time.sleep(0.5)
                        else:
                            skipped_count += 1
                        
                    progress_bar.progress(1.0)
                    st.session_state.geo_sub_locations_searched = list(set(searched + sub_locs_to_search))
                
                    if added_count > 0:
                        status_placeholder.success(f"✅ Success! Discovered and added **{added_count}** new enriched leads to '{master_sheet_name}' (skipped {skipped_count} leads without emails).")
                    else:
                        status_placeholder.warning(f"Processed {total_to_process} businesses, but found no emails. Try a different category or search location.")
                    
                    clear_cache()
                    time.sleep(3)
                    st.rerun()

def render_chat_assistant():
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
                            subject, body, campaign_used = draft_email_with_deepseek(company, scraped_text)
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
                            subject, body, _ = draft_email_with_deepseek(company, scraped_text)
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
                    st.session_state.messages.append({"role": "assistant", "content": f"❌ Discarded draft for {draft['company']}."})
                st.rerun()
def render_tables():
    
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
                                        if last_contacted_idx != -1:
                                            update_data.append({'range': rowcol_to_a1(row_idx, last_contacted_idx + 1), 'values': [[datetime.now().strftime("%Y-%m-%d")]]})
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
                                    if last_contacted_idx != -1:
                                        worksheet.update_acell(rowcol_to_a1(row_idx, last_contacted_idx + 1), datetime.now().strftime("%Y-%m-%d"))
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
                                followup_subj, followup_body, _ = draft_email_with_deepseek(company, scraped_text, is_follow_up=True)
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

# ==============================================================================
# MAIN ROUTING
# ==============================================================================
page = st.sidebar.radio("📌 Navigation", ["📊 Dashboard", "⚡ Outreach Jobs", "🌍 Geo-Sourcing", "⚙️ Campaigns", "💬 AI Assistant"])

if page == "📊 Dashboard":
    render_dashboard()
    render_tables()
elif page == "⚡ Outreach Jobs":
    render_command_center()
elif page == "🌍 Geo-Sourcing":
    render_geo_sourcing()
elif page == "⚙️ Campaigns":
    render_campaigns()
elif page == "💬 AI Assistant":
    render_chat_assistant()
