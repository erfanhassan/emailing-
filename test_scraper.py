import os
from dotenv import load_dotenv
import scraper

websites = [
    'http://www.thegreenloungebd.co/',
    'http://www.intercontinental.com/dhaka',
    'https://www.ihg.com/holidayinn/hotels/us/en/dhaka/dachi/hoteldetail/dining',
    'https://birdseyerestaurants.com/menu/',
    'https://thaichirestaurantcafe.shop/',
    'https://www.treehousebd.com/',
    'http://www.saffron.business.site/',
    'https://www.marriott.com/hotels/hotel-information/restaurant/dacsi-sheraton-dhaka/'
]

for w in websites:
    print(f"Scraping {w}...")
    text, emails = scraper.scrape_website_data(w)
    print(f"Found emails: {emails}")
