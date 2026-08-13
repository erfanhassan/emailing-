import requests
from bs4 import BeautifulSoup
import re

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def search_google(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    
    for g in soup.find_all('div', class_='g'):
        a = g.find('a')
        link = a['href'] if a else ""
        text = g.text
        print("Link:", link)
        print("Text:", text)
        print("Emails:", re.findall(EMAIL_REGEX, text))
        print("---")

if __name__ == '__main__':
    search_google('site:facebook.com OR site:instagram.com "The Local Bakery" New York email')
