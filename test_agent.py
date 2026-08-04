import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from ai_agent import draft_email_with_deepseek

company = "Apple"
website_text = "Apple Inc. is an American multinational technology company that specializes in consumer electronics, software and online services."
subject, body = draft_email_with_deepseek(company, website_text)

print("SUBJECT:", subject)
print("BODY:")
print(body)
