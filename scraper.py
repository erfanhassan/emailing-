import re
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
import urllib3
from duckduckgo_search import DDGS

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

def find_social_media_contact(business_name: str, location: str) -> tuple[str, list, str]:
    """
    Search for a business on Facebook or Instagram via DuckDuckGo and extract email/phone if possible.
    Returns (social_url, [emails], phone)
    """
    query = f'"{business_name}" "{location}" email (site:facebook.com OR site:instagram.com)'
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=3)
            emails = set()
            url = ""
            phone = ""
            
            for r in results:
                text = r.get("body", "") + " " + r.get("title", "")
                found_emails = re.findall(EMAIL_REGEX, text)
                for e in found_emails:
                    if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        emails.add(e.lower())
                
                # Try finding phone numbers like (123) 456-7890 or 123-456-7890 in text
                found_phones = re.findall(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', text)
                if found_phones and not phone:
                    phone = found_phones[0]
                
                if not url:
                    url = r.get("href", "")
                    
            if url and not emails:
                try:
                    # Attempt to scrape the Facebook /about page directly
                    import requests
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    
                    if "facebook.com" in parsed.netloc:
                        base_fb = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if base_fb.endswith('/'): base_fb = base_fb[:-1]
                        about_url = f"{base_fb}/about"
                        
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        resp = requests.get(about_url, headers=headers, timeout=10)
                        
                        if resp.status_code == 200:
                            page_text = resp.text
                            found_fb_emails = re.findall(EMAIL_REGEX, page_text)
                            for e in found_fb_emails:
                                if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                                    emails.add(e.lower())
                            
                            found_fb_phones = re.findall(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', page_text)
                            if found_fb_phones and not phone:
                                phone = found_fb_phones[0]
                except Exception as e:
                    logger.warning(f"Failed to scrape FB about page: {e}")
                    
            return url, list(emails), phone
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return "", [], ""

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
