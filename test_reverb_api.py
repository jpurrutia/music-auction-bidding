#!/usr/bin/env python
"""
Test script for Reverb API integration
Run this to verify your API token and see market price data
"""

from market_scraper import MarketScraper
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api():
    """Test the Reverb API integration"""
    # Check if token is set
    token = os.getenv("REVERB_API_TOKEN")
    if not token:
        print("ERROR: No Reverb API token found in .env file")
        print("Please add your token to the .env file and try again")
        return
    
    print(f"API Token found: {token[:5]}...{token[-4:] if len(token) > 8 else ''}")
    
    # Create scraper
    scraper = MarketScraper()
    
    # Test with a few different instrument types
    test_items = [
        "Gibson Les Paul Standard",
        "Fender Stratocaster American",
        "Martin D-28 Acoustic Guitar",
        "Roland Jazz Chorus JC-120 Amp"
    ]
    
    print("\nTesting Reverb API search...")
    for item in test_items:
        print(f"\nSearching for: {item}")
        result = scraper.get_market_price(item, refresh_cache=True)
        
        if result and result.get("source_type") == "reverb_api":
            print("✅ SUCCESS: Found results from Reverb API")
            print(f"  - Average price: ${result.get('average_price', 0):.2f}")
            print(f"  - Median price: ${result.get('median_price', 0):.2f}")
            print(f"  - Price range: ${result.get('min_price', 0):.2f} - ${result.get('max_price', 0):.2f}")
            print(f"  - Results count: {result.get('count', 0)}")
            
            # Print sample listings
            samples = result.get("sample_listings", [])
            if samples:
                print("\n  Sample listings:")
                for i, sample in enumerate(samples, 1):
                    print(f"  {i}. {sample.get('title')} - ${sample.get('price'):.2f} ({sample.get('condition')})")
        else:
            print("❌ API search failed, falling back to simulation")
            if result:
                print(f"  - Simulated price: ${result.get('average_price', 0):.2f}")
    
    print("\nTest complete!")

if __name__ == "__main__":
    test_api()
