#!/usr/bin/env python3
"""
Test script for eBay API integration and web scraping in the MarketScraper
"""
import os
import json
from market_scraper import MarketScraper
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Main test function"""
    print("Testing eBay market price sources")
    
    # Create a market scraper instance
    scraper = MarketScraper()
    
    # Check if eBay API is properly initialized
    print(f"eBay SDK Available: {scraper.ebay_enabled}")
    if not scraper.ebay_enabled:
        print("eBay API is not enabled. Will use web scraping instead.")
        print("For full API testing, you need:")
        print("1. The ebaysdk package (already installed)")
        print("2. Set up the required environment variables in .env file:")
        print("   - EBAY_APP_ID")
        print("   - EBAY_CERT_ID")
        print("   - EBAY_DEV_ID")
    
    # Test items to search for
    test_items = [
        "Fender Stratocaster",  # Common guitar
        "Boss DS-1 Distortion Pedal",  # Common pedal
        "Audio Technica AT2020",  # Common mic
        "Gibson SG"  # Another popular guitar
    ]
    
    # Try each data source
    for item in test_items:
        print(f"\n{'=' * 60}")
        print(f"TESTING ITEM: {item}")
        print(f"{'=' * 60}")
        
        # Try direct web scraping with pagination
        print("\n1. Testing eBay web scraping with pagination:")
        print("----------------------------------------")
        try:
            # Test with higher max_results to see pagination in action
            scrape_result = scraper.search_ebay_scrape(item, max_results=25, max_pages=2)
            if scrape_result and 'average_price' in scrape_result:
                # Check what field name is used for the source
                source = scrape_result.get('source', scrape_result.get('source_type', 'unknown'))
                print(f"✓ Success! Source: {source}")
                print(f"Found {scrape_result.get('count', 0)} listings across multiple pages")
                print(f"Average price: ${scrape_result.get('average_price', 0):.2f}")
                print(f"Median price: ${scrape_result.get('median_price', 0):.2f}")
                print(f"Price range: ${scrape_result.get('min_price', 0):.2f} - ${scrape_result.get('max_price', 0):.2f}")

                
                # Get condition distribution
                condition_counts = scrape_result.get('condition_counts', {})
                if condition_counts:
                    print("\nCondition distribution:")
                    for condition, count in condition_counts.items():
                        print(f"  - {condition}: {count} listings")
                
                # Print sample listings
                samples = scrape_result.get('sample_listings', [])
                if samples:
                    print("\nSample listings (first 5):")
                    for i, sample in enumerate(samples[:5], 1):
                        print(f"{i}. {sample['title'][:50]}... - ${sample['price']:.2f} ({sample['condition']})")
            else:
                print("✗ No results from eBay web scraping")
        except Exception as e:
            print(f"✗ Error testing eBay scraping: {str(e)}")
            import traceback
            traceback.print_exc()
            
        # Try the API method (will use API or fallback to scraping or simulation)
        print("\n2. Testing eBay API or fallback chain:")
        print("----------------------------------")
        try:
            ebay_result = scraper.search_ebay_api(item)
            if ebay_result:
                source = ebay_result.get('source_type', 'unknown')
                print(f"✓ Success! Source: {source}")
                print(f"Found {ebay_result.get('count', 0)} listings")
                print(f"Average price: ${ebay_result.get('average_price', 0):.2f}")
                print(f"Median price: ${ebay_result.get('median_price', 0):.2f}")
            else:
                print("✗ No results from any eBay source")
        except Exception as e:
            print(f"✗ Error testing eBay API chain: {str(e)}")
        
        # Try integrated market price search
        print("\n3. Using integrated market price search:")
        print("-----------------------------------")
        try:
            market_result = scraper.get_market_price(item)
            source_type = market_result.get('source_type', 'unknown')
            print(f"✓ Success! Source: {source_type}")
            print(f"Confidence level: {market_result.get('confidence_level', 0)}%")
            print(f"Average price: ${market_result.get('average_price', 0):.2f}")
            
            # Check if eBay data was included in sources
            sources = market_result.get('sources', {})
            
            # Display all sources
            print("\nData sources used:")
            for source_name, price in sources.items():
                print(f"  - {source_name}: ${price:.2f}")
                
        except Exception as e:
            print(f"✗ Error testing integrated search: {str(e)}")
        
        print(f"\n{'=' * 60}\n")

if __name__ == "__main__":
    main()
