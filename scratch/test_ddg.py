import re
from duckduckgo_search import DDGS

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def find_social_media_contact(business_name, location):
    query = f'"{business_name}" "{location}" (site:facebook.com OR site:instagram.com)'
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=3)
            emails = set()
            phone = ""
            url = ""
            for r in results:
                print(r)
                text = r.get("body", "") + " " + r.get("title", "")
                found_emails = re.findall(EMAIL_REGEX, text)
                for e in found_emails:
                    if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        emails.add(e.lower())
                
                # very simple phone extraction attempt for local formats if available
                # or just look for email
                if not url:
                    url = r.get("href", "")
            return url, list(emails), phone
    except Exception as e:
        print(e)
        return "", [], ""

if __name__ == '__main__':
    print(find_social_media_contact("The Local Bakery", "New York"))
