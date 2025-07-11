#!/usr/bin/env python3
"""
Market Scraper - Finds market prices for musical instruments from popular sites
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List, Tuple
import time
import os
import json
import re
import random
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MarketScraper:
    def __init__(self, cache_dir: str = "cache"):
        """Initialize the market scraper with cache directory"""
        # Set up cache directory
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "market_prices.json")
        
        # Reverb API settings - set these first
        self.api_token = os.getenv("REVERB_API_TOKEN")
        self.use_sandbox = os.getenv("USE_SANDBOX", "False").lower() == "true"
        self.base_domain = "sandbox.reverb.com" if self.use_sandbox else "api.reverb.com"
        self.base_url = f"https://{self.base_domain}/api"
        self.cache_expiry_days = int(os.getenv("CACHE_EXPIRY_DAYS", "7"))
        
        # Now set up headers after API token is loaded
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/hal+json",
            "Accept-Version": "3.0",
            "Content-Type": "application/hal+json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Add authorization if token exists
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"
            
        # Create separate headers for scraping (without auth)
        self.scrape_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Load cache if it exists
        self.price_cache = {}
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.price_cache = json.load(f)
        
        # Reverb API settings
        self.api_token = os.getenv("REVERB_API_TOKEN")
        self.use_sandbox = os.getenv("USE_SANDBOX", "False").lower() == "true"
        self.base_domain = "sandbox.reverb.com" if self.use_sandbox else "api.reverb.com"
        self.base_url = f"https://{self.base_domain}/api"
        self.cache_expiry_days = int(os.getenv("CACHE_EXPIRY_DAYS", "7"))

    def save_cache(self):
        """Save the price cache to file"""
        with open(self.cache_file, 'w') as f:
            json.dump(self.price_cache, f)
    
    def clean_description(self, description: str) -> str:
        """Clean item description to get better search results"""
        # Remove case details and other common phrases
        cleaned = re.sub(r'w/\s+(Hardshell|Chipboard)?\s*Case', '', description, flags=re.IGNORECASE)
        cleaned = re.sub(r'w/\s+Bag', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bNOS\b', '', cleaned)  # New Old Stock
        cleaned = re.sub(r'\bNew\b', '', cleaned)
        cleaned = re.sub(r'\bRetail\b', '', cleaned)
        return cleaned.strip()
    
    def get_market_price(self, item_description: str, refresh_cache=False) -> dict:
        """Get market price for an item using Reverb API or simulation"""
        # Check cache first if not forcing refresh
        cache_key = self.clean_description(item_description).lower()
        
        if not refresh_cache and cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            # Check if cache is still valid based on expiry setting
            cache_date = datetime.fromisoformat(cached_data.get("timestamp"))
            if datetime.now() - cache_date < timedelta(days=self.cache_expiry_days):
                return cached_data
        
        # Try Reverb API first if token exists
        result = None
        if self.api_token:
            try:
                result = self.search_reverb_api(item_description)
                if result:
                    print(f"Found price data from Reverb API for: {item_description}")
            except Exception as e:
                print(f"Error using Reverb API: {str(e)}")
        
        # Fall back to simulated data if API fails or no token
        if not result:
            print(f"Using simulated price data for: {item_description}")
            reverb_price = self.search_reverb(item_description)  # Simulated
            ebay_price = self.search_ebay(item_description)      # Simulated
            sweetwater_price = self.search_sweetwater(item_description)  # Simulated
            
            # Calculate weighted average (giving more weight to Reverb for musical instruments)
            prices = [p for p in [reverb_price, ebay_price, sweetwater_price] if p is not None]
            if prices:
                result = {
                    "average_price": sum(prices) / len(prices),
                    "min_price": min(prices),
                    "max_price": max(prices),
                    "count": len(prices),
                    "sources": {
                        "reverb": reverb_price,
                        "ebay": ebay_price,
                        "sweetwater": sweetwater_price
                    },
                    "source_type": "simulation",
                    "timestamp": datetime.now().isoformat()
                }
        
        # Store result in cache if we got one
        if result:
            self.price_cache[cache_key] = result
            self.save_cache()
        
        return result

    def search_reverb_api(self, item_description: str, max_results=10) -> dict:
        """Search Reverb.com for market prices using the official API"""
        # Clean up item description for better search results
        query = self.clean_description(item_description)
        
        try:
            # Print debug info
            print(f"Using Reverb API at: {self.base_url}")
            print(f"Authorization header: {'Set' if 'Authorization' in self.headers else 'Not set'}")
            
            # Make API request to search listings
            url = f"{self.base_url}/listings"
            params = {
                "query": quote_plus(query),
                "per_page": max_results
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                listings = data.get("listings", [])
                
                if listings:
                    # Extract prices and other data from listings
                    prices = []
                    conditions = []
                    titles = []
                    urls = []
                    
                    for listing in listings:
                        price_info = listing.get("price", {})
                        condition_info = listing.get("condition", {})
                        
                        if price_info:
                            price = float(price_info.get("amount", 0))
                            condition = condition_info.get("display_name", "Unknown")
                            title = listing.get("title", "")
                            url = listing.get("_links", {}).get("self", {}).get("href", "")
                            
                            prices.append(price)
                            conditions.append(condition)
                            titles.append(title)
                            urls.append(url)
                    
                    if prices:
                        # Calculate statistics
                        prices.sort()  # For median calculation
                        median_index = len(prices) // 2
                        median = prices[median_index] if len(prices) % 2 == 1 else (prices[median_index-1] + prices[median_index]) / 2
                        
                        # Analyze conditions
                        condition_counts = {}
                        for condition in conditions:
                            if condition:
                                condition_counts[condition] = condition_counts.get(condition, 0) + 1
                        
                        # Format sample listings
                        samples = []
                        for i in range(min(3, len(prices))):
                            samples.append({
                                "title": titles[i],
                                "price": prices[i],
                                "condition": conditions[i],
                                "url": urls[i]
                            })
                        
                        # Return comprehensive result
                        return {
                            "average_price": sum(prices) / len(prices),
                            "median_price": median,
                            "min_price": min(prices),
                            "max_price": max(prices),
                            "count": len(prices),
                            "conditions": condition_counts,
                            "sample_listings": samples,
                            "source_type": "reverb_api",
                            "timestamp": datetime.now().isoformat()
                        }
            
            print(f"API request failed with status code: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            return None
                
        except Exception as e:
            print(f"Error searching Reverb API: {str(e)}")
            return None

    def search_reverb(self, item_description: str) -> float:
        """Search Reverb.com for prices (simulated for demo)"""
        # In a real implementation, this would actually scrape Reverb.com
        # For now, we'll simulate it with some realistic pricing logic
        cleaned = self.clean_description(item_description).lower()
        
        # Extract brand and instrument type
        brands = ["fender", "gibson", "martin", "taylor", "prs", "ibanez", "epiphone", 
                 "squier", "gretsch", "jackson", "charvel", "yamaha", "korg", "roland"]
        brand = next((b for b in brands if b in cleaned), None)
        
        is_guitar = any(x in cleaned for x in ["guitar", "stratocaster", "telecaster", "les paul", "sg"])
        is_acoustic = "acoustic" in cleaned
        is_bass = "bass" in cleaned
        is_amp = any(x in cleaned for x in ["amp", "amplifier"])
        is_pedal = any(x in cleaned for x in ["pedal", "effect", "delay", "distortion", "overdrive"])
        is_keyboard = any(x in cleaned for x in ["keyboard", "piano", "synth", "synthesizer", "nord"])
        is_drum = any(x in cleaned for x in ["drum", "snare", "cymbal", "hi-hat", "kick"])
        
        # Base price depends on instrument type and brand
        if is_guitar:
            if brand in ['gibson', 'fender', 'prs', 'martin', 'taylor']:
                base_price = random.uniform(800, 3000)
            else:
                base_price = random.uniform(300, 1200)
                
            if is_acoustic:
                base_price *= 1.2  # Acoustic guitars often cost a bit more
                
        elif is_bass:
            if brand in ['fender', 'gibson']:
                base_price = random.uniform(700, 1800)
            else:
                base_price = random.uniform(250, 900)
                
        elif is_amp:
            if brand in ['fender', 'marshall', 'vox', 'mesa']:
                base_price = random.uniform(500, 2200)
            else:
                base_price = random.uniform(200, 800)
                
        elif is_pedal:
            base_price = random.uniform(80, 350)
            
        elif is_keyboard:
            if "nord" in cleaned or "moog" in cleaned:
                base_price = random.uniform(1200, 3500)
            else:
                base_price = random.uniform(400, 1500)
                
        elif is_drum:
            base_price = random.uniform(300, 1200)
            
        else:
            # Generic calculation
            base_price = random.uniform(200, 1000)
            
        # Add some randomness to make it more realistic
        variation = random.uniform(0.9, 1.1)
        final_price = base_price * variation
        
        return round(final_price, 2)

    def search_ebay(self, query: str) -> Optional[float]:
        """Search eBay for prices (simulated for demo)"""
        # Simulate a slight price difference from Reverb
        reverb_price = self.search_reverb(query)
        if reverb_price:
            # eBay prices tend to be a bit lower
            return round(reverb_price * random.uniform(0.85, 0.95))
        return None
    
    def search_sweetwater(self, query: str) -> Optional[float]:
        """Search Sweetwater for prices (simulated for demo)"""
        # Simulate retail prices (generally higher and more consistent)
        reverb_price = self.search_reverb(query)
        if reverb_price:
            # Retail prices tend to be higher and more standardized
            return round(reverb_price * random.uniform(1.1, 1.3))
        return None


# Example usage
if __name__ == "__main__":
    scraper = MarketScraper()
    test_items = [
        "Gibson Les Paul Standard",
        "Fender Stratocaster",
        "Boss DD-7 Digital Delay",
        "Taylor 814ce"
    ]
    
    for item in test_items:
        print(f"Finding market price for: {item}")
        result = scraper.get_market_price(item)
        print(f"Results: {json.dumps(result, indent=2)}")
        print("---")
