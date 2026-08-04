import re
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def _scrape_page(url: str, timeout: int = 15) -> tuple[str, set]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        emails = set()
        
        for a in soup.find_all('a', href=True):
            if a['href'].startswith('mailto:'):
                email = a['href'].replace('mailto:', '').split('?')[0].strip()
                if email:
                    emails.add(email)
                    
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        
        found_emails = re.findall(EMAIL_REGEX, text)
        for e in found_emails:
            if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                emails.add(e.lower())
                
        return text, emails
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return "", set()

def scrape_website_data(url: str, timeout: int = 15) -> tuple[str, list]:
    """
    Scrapes visible text and attempts to find emails from the given URL.
    Returns (truncated_text, list_of_emails).
    """
    if not url.startswith('http'):
        url = 'https://' + url
        
    text, emails = _scrape_page(url, timeout)
    
    if not emails:
        # Try common contact pages if homepage didn't have an email
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        for path in ['/contact', '/contact-us', '/about', '/terms']:
            contact_url = urljoin(base_url, path)
            c_text, c_emails = _scrape_page(contact_url, timeout)
            emails.update(c_emails)
            if c_emails:
                break
                
    return text[:5000], list(emails)
