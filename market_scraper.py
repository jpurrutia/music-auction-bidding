#!/usr/bin/env python3
"""
Market Scraper - Finds market prices for musical instruments from popular sites
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List, Tuple
import time
import json
import os
import re
import random
from urllib.parse import quote_plus

class MarketScraper:
    def __init__(self, cache_dir: str = "cache"):
        """Initialize the market scraper with cache directory"""
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "market_prices.json")
        
        # Headers to avoid bot detection
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        # Load cache if it exists
        self.price_cache = {}
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.price_cache = json.load(f)
    
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
    
    def get_market_price(self, item_description: str, force_refresh: bool = False) -> Dict:
        """
        Get market price for an item from various sources
        Returns a dictionary with prices and sources
        """
        # Check cache first unless force refresh
        cache_key = item_description.lower().strip()
        if not force_refresh and cache_key in self.price_cache:
            return self.price_cache[cache_key]
        
        cleaned_description = self.clean_description(item_description)
        
        # Initialize results
        results = {
            "reverb": self.search_reverb(cleaned_description),
            "ebay": self.search_ebay(cleaned_description),
            "sweetwater": self.search_sweetwater(cleaned_description)
        }
        
        # Calculate average price from available sources
        prices = [price for source, price in results.items() if price is not None]
        if prices:
            results["average"] = sum(prices) / len(prices)
        else:
            results["average"] = None
            
        # Cache the results
        self.price_cache[cache_key] = results
        self.save_cache()
        
        return results

    def search_reverb(self, query: str) -> Optional[float]:
        """Search Reverb.com for prices (simulated for demo)"""
        # In a real implementation, this would actually scrape Reverb.com
        # For now, we'll simulate it with some realistic pricing logic
        time.sleep(0.5)  # Simulate network delay
        
        # Extract brand and instrument type for better price estimation
        brand_match = re.search(r'(Gibson|Fender|Martin|Taylor|PRS|Gretsch|Ibanez|Epiphone|Roland|Boss)', query)
        brand = brand_match.group(1) if brand_match else ""
        
        is_guitar = any(term in query.lower() for term in ['guitar', 'strat', 'les paul', 'telecaster', 'sg'])
        is_bass = 'bass' in query.lower()
        is_amp = any(term in query.lower() for term in ['amp', 'amplifier'])
        is_pedal = any(term in query.lower() for term in ['pedal', 'effect', 'delay', 'reverb', 'overdrive'])
        
        # Base price ranges by category
        if is_guitar:
            if brand in ['Gibson', 'Fender', 'PRS', 'Martin', 'Taylor']:
                base_price = random.uniform(800, 3000)
            else:
                base_price = random.uniform(300, 1200)
        elif is_bass:
            if brand in ['Fender', 'Gibson']:
                base_price = random.uniform(700, 2500)
            else:
                base_price = random.uniform(400, 1000)
        elif is_amp:
            base_price = random.uniform(300, 1500)
        elif is_pedal:
            base_price = random.uniform(80, 300)
        else:
            base_price = random.uniform(200, 800)
            
        # Add some randomness to simulate market variance
        return round(base_price * random.uniform(0.9, 1.1))
    
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
