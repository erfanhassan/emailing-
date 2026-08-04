import requests
from bs4 import BeautifulSoup
import re

url = "https://www.treehousebd.com/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
response = requests.get(url, headers=headers)
print("Status:", response.status_code)
html = response.text
print("HTML length:", len(html))

soup = BeautifulSoup(html, 'html.parser')
text = soup.get_text(separator=' ', strip=True)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
found_emails = set(re.findall(EMAIL_REGEX, text))
print("Regex emails in text:", found_emails)

for a in soup.find_all('a', href=True):
    if 'mailto' in a['href']:
        print("Mailto link:", a['href'])
        
import scraper
print("Scraper returned:", scraper.scrape_website_data(url))
