#!/usr/bin/env python
"""
Test script for Reverb API integration

This script helps verify your Reverb API configuration and test market price data retrieval.
It can run predefined tests or search for specific instruments based on command-line arguments.

Usage:
    python test_reverb_api.py                  # Run standard test suite
    python test_reverb_api.py --search "Gibson Les Paul"  # Search for specific item
    python test_reverb_api.py --clear-cache    # Clear the cache before testing
    python test_reverb_api.py --verbose        # Show detailed API response info
"""

import argparse
import json
import os
import sys
import time
from dotenv import load_dotenv
from pathlib import Path

# Import our market scraper
from market_scraper import MarketScraper

# Load environment variables
load_dotenv()

# Set up argument parser
def parse_args():
    parser = argparse.ArgumentParser(
        description="Test Reverb API integration and search functionality"
    )
    parser.add_argument(
        "--search", "-s",
        help="Search for a specific instrument instead of running test suite"
    )
    parser.add_argument(
        "--clear-cache", "-c",
        action="store_true",
        help="Clear the cache before running tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show more detailed output including API response info"
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=5,
        help="Number of sample listings to display (default: 5)"
    )
    return parser.parse_args()


def clear_cache():
    """Clear the API response cache"""
    cache_dir = Path("cache")
    if not cache_dir.exists():
        print("Cache directory not found. Nothing to clear.")
        return
    
    count = 0
    for file in cache_dir.glob("*.json"):
        file.unlink()
        count += 1
    
    print(f"Cleared {count} cache files")


def validate_api_token():
    """Check if the API token is properly configured"""
    token = os.getenv("REVERB_API_TOKEN")
    if not token:
        print("\n❌ ERROR: No Reverb API token found in environment variables")
        print("Please create a .env file with your REVERB_API_TOKEN and try again.")
        print("Example .env file content:")
        print("REVERB_API_TOKEN=your_token_here")
        print("USE_SANDBOX=false")
        print("CACHE_EXPIRY_DAYS=7")
        return False
    
    # Mask most of the token for security
    visible_chars = min(4, len(token) // 4)
    masked_token = token[:visible_chars] + "*" * (len(token) - (visible_chars * 2)) + token[-visible_chars:]
    print(f"✅ API Token found: {masked_token}")
    return True


def format_market_data(result, verbose=False, sample_count=5):
    """Format market data results for display"""
    if not result:
        return "❌ No results returned"
    
    output = []
    
    # Determine if this is real API data or fallback simulation
    source_type = result.get("source_type", "unknown")
    is_api_data = source_type == "reverb_api"
    
    # Header
    if is_api_data:
        output.append("✅ SUCCESS: Found results from Reverb API")
    else:
        output.append(f"⚠️ NOTICE: Using simulated data ({source_type})")
    
    # Price information
    output.append(f"  - Average price: ${result.get('average_price', 0):.2f}")
    output.append(f"  - Median price: ${result.get('median_price', 0):.2f}")
    output.append(f"  - Price range: ${result.get('min_price', 0):.2f} - ${result.get('max_price', 0):.2f}")
    output.append(f"  - Results count: {result.get('count', 0)}")
    
    # Additional market metrics
    if 'data_confidence' in result:
        output.append(f"  - Data confidence: {result.get('data_confidence')}%")
    if 'market_volatility' in result:
        output.append(f"  - Market volatility: {result.get('market_volatility', 'Unknown')}")
    
    # Condition breakdown
    conditions = result.get("condition_breakdown", {})
    if conditions and verbose:
        output.append("\n  Condition breakdown:")
        for condition, count in conditions.items():
            output.append(f"  - {condition}: {count} listings")
    
    # Cache information
    if verbose and 'timestamp' in result:
        cache_time = result.get("timestamp", "Unknown")
        output.append(f"\n  Cache timestamp: {cache_time}")
    
    # Sample listings
    samples = result.get("sample_listings", [])
    if samples:
        # Limit the number of samples to display
        display_samples = samples[:sample_count]
        output.append("\n  Sample listings:")
        for i, sample in enumerate(display_samples, 1):
            output.append(f"  {i}. {sample.get('title')} - ${sample.get('price'):.2f} ({sample.get('condition')})")
            if verbose and 'url' in sample:
                output.append(f"     URL: {sample.get('url')}")
    
    return "\n".join(output)


def test_api(custom_search=None, clear_cache_first=False, verbose=False, sample_count=5):
    """Test the Reverb API integration"""
    # Validate API token first
    if not validate_api_token():
        return False
    
    # Create scraper
    try:
        scraper = MarketScraper()
    except Exception as e:
        print(f"\n❌ ERROR: Failed to initialize MarketScraper: {e}")
        return False
    
    # Clear cache if requested
    if clear_cache_first:
        clear_cache()
    
    # If custom search is provided, only test that
    if custom_search:
        test_items = [custom_search]
    else:
        # Test with a diverse set of instrument types
        test_items = [
            "Gibson Les Paul Standard",
            "Fender Stratocaster American",
            "Martin D-28 Acoustic Guitar",
            "Roland Jazz Chorus JC-120 Amp",
            "Moog Subsequent 37 Synthesizer"
        ]
    
    # Run the searches
    success_count = 0
    api_success_count = 0
    print(f"\nTesting Reverb API with {len(test_items)} search queries...")
    
    for item in test_items:
        print(f"\n{'-'*50}")
        print(f"Searching for: {item}")
        
        # Show a simple spinner while waiting for API
        if not verbose:
            print("Fetching data", end="")
            for _ in range(3):
                time.sleep(0.3)
                print(".", end="", flush=True)
            print()
        
        try:
            result = scraper.get_market_price(item, refresh_cache=clear_cache_first)
            
            # Check if this is API data or simulated
            if result:
                success_count += 1
                if result.get("source_type") == "reverb_api":
                    api_success_count += 1
                
                # Print the formatted results
                print(format_market_data(result, verbose, sample_count))
            else:
                print("❌ No results returned from scraper")
                
        except Exception as e:
            print(f"❌ ERROR: Search failed with exception: {e}")
    
    # Print summary
    print(f"\n{'-'*50}")
    print("Test Summary:")
    print(f"  - Total searches: {len(test_items)}")
    print(f"  - Successful searches: {success_count}")
    print(f"  - API data: {api_success_count}")
    print(f"  - Simulated data: {success_count - api_success_count}")
    
    # Return True if at least one search succeeded
    return success_count > 0


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_args()
    
    # Run the API test
    success = test_api(
        custom_search=args.search,
        clear_cache_first=args.clear_cache,
        verbose=args.verbose,
        sample_count=args.count
    )
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)
