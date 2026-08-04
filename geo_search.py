import requests
import urllib.parse
import os
import logging
from openai import OpenAI
import json
import time

logger = logging.getLogger(__name__)

def get_sub_locations(location: str, exclude_list: list = None) -> list[str]:
    """
    Retrieves 10 major commercial neighborhoods/sub-locations for the target city using DeepSeek.
    Includes a robust local fallback if the API is unavailable or fails.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("No DEEPSEEK_API_KEY found. Using fallback sub-locations.")
        return get_fallback_sub_locations(location)
        
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
    exclude_str = f" Excluding the following: {', '.join(exclude_list)}." if exclude_list else ""
    prompt = f"""
Return a JSON object with a single key "sub_locations" containing a list of 10 major commercial neighborhoods, districts, or sub-regions of: "{location}".{exclude_str}
Each sub-location should be formatted as "Neighborhood, Location" (e.g. "Gulshan, Dhaka" or "Manhattan, New York").
Return ONLY a valid JSON object. No markdown formatting, no backticks.
Format:
{{"sub_locations": ["Neighborhood 1, City", "Neighborhood 2, City", ...]}}
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": "You are a JSON-only helper."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        sub_locs = data.get("sub_locations", [])
        if sub_locs:
            return sub_locs
    except Exception as e:
        logger.error(f"Error calling DeepSeek for sub-locations: {e}")
        
    return get_fallback_sub_locations(location)

def get_fallback_sub_locations(location: str) -> list[str]:
    """
    Standard commercial neighborhoods lookup for common cities.
    """
    loc_clean = location.lower().strip()
    if "dhaka" in loc_clean:
        return [
            "Gulshan, Dhaka", "Dhanmondi, Dhaka", "Banani, Dhaka", 
            "Uttara, Dhaka", "Mirpur, Dhaka", "Motijheel, Dhaka", 
            "Tejgaon, Dhaka", "Mohakhali, Dhaka", "Wari, Dhaka", "Badda, Dhaka"
        ]
    elif "new york" in loc_clean or "nyc" in loc_clean:
        return [
            "Manhattan, New York", "Brooklyn, New York", "Queens, New York", 
            "Bronx, New York", "Staten Island, New York", "Astoria, New York", 
            "Flushing, New York", "Williamsburg, New York", "Harlem, New York", "SoHo, New York"
        ]
    elif "chittagong" in loc_clean or "chatogram" in loc_clean:
        return [
            "GEC Circle, Chittagong", "Agrabad, Chittagong", "Halishahar, Chittagong",
            "Nasirabad, Chittagong", "Panchlaish, Chittagong", "Chawkbazar, Chittagong"
        ]
    else:
        return [
            location,
            f"Downtown {location}",
            f"Central {location}",
            f"Commercial District, {location}",
            f"North {location}",
            f"South {location}",
            f"East {location}",
            f"West {location}"
        ]

def discover_businesses(location: str, industry: str) -> list[dict]:
    """
    Search for businesses in a location using Google Places API with pagination.
    Returns a list of dicts: [{'name': '...', 'website': '...', 'phone': '...', 'address': '...'}]
    """
    api_key = os.environ.get("PLACES_API_KEY", "")
    
    if not api_key:
        logger.info(f"No PLACES_API_KEY found. Using simulated data for {industry} in {location}.")
        return [
            {
                "name": f"Example {industry.title()} ({location})",
                "website": "https://www.example.com",
                "phone": "+1-555-0199",
                "address": f"123 Commercial Rd, {location}"
            },
            {
                "name": f"Python Software Foundation ({location})",
                "website": "https://www.python.org/about/contact/",
                "phone": "+1-555-0200",
                "address": f"456 PSF Way, {location}"
            }
        ]
        
    logger.info(f"Using Google Places API to search for {industry} in {location}...")
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.websiteUri,places.nationalPhoneNumber,places.formattedAddress"
    }
    
    results = []
    next_page_token = None
    
    # Places API supports up to 3 pages (60 results total per single query)
    for page in range(3):
        data = {
            "textQuery": f"{industry} in {location}"
        }
        if next_page_token:
            data["pageToken"] = next_page_token
            
        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response_data = response.json()
            
            if "error" in response_data:
                logger.error(f"Google Places API Error on page {page+1}: {response_data['error']}")
                break
                
            places = response_data.get("places", [])
            page_results_count = 0
            
            for place in places:
                name = place.get("displayName", {}).get("text", "")
                website = place.get("websiteUri", "")
                phone = place.get("nationalPhoneNumber", "")
                address = place.get("formattedAddress", "")
                
                # Filter out social media domains masquerading as official websites
                social_domains = ["youtube.com", "facebook.com", "instagram.com", "twitter.com", "linkedin.com", "tiktok.com"]
                is_social = any(domain in website.lower() for domain in social_domains) if website else True
                
                if name and website and not is_social:
                    results.append({
                        "name": name,
                        "website": website,
                        "phone": phone,
                        "address": address
                    })
                    page_results_count += 1
                    
            logger.info(f"Page {page+1}: Found {len(places)} places, {page_results_count} valid leads.")
            
            next_page_token = response_data.get("nextPageToken")
            if not next_page_token:
                break
                
            # Sleep briefly to respect API rate limits
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error calling Google Places API on page {page+1}: {e}")
            break
            
    return results
