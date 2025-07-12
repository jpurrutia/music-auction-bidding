#!/usr/bin/env python3
"""
Script to gather test data for the price analyzer using the market scraper
"""

import os
import json
from market_scraper import MarketScraper

def main():
    """Gather test market price data for analysis"""
    print("Gathering test market price data...")
    
    # Create market scraper instance
    scraper = MarketScraper()
    
    # List of music gear to test with
    test_items = [
        "Fender Stratocaster American Professional II",
        "Gibson Les Paul Standard 60s",
        "Boss DS-1 Distortion Pedal",
        "Shure SM58 Microphone",
        "Audio Technica AT2020 Condenser Mic",
        "Korg Minilogue Synthesizer",
        "Yamaha P-45 Digital Piano",
        "Akai MPK Mini MK3 MIDI Controller",
        "JBL 305P MKII Studio Monitor",
        "Behringer X32 Digital Mixer"
    ]
    
    print(f"Fetching market prices for {len(test_items)} items...")
    
    # Process each test item
    results = {}
    for item in test_items:
        print(f"\nProcessing: {item}")
        # Get market price data with caching enabled
        price_data = scraper.get_market_price(item)
        if price_data:
            results[item] = price_data
            print(f"- Found price: ${price_data['price']:.2f}")
            if 'source' in price_data:
                print(f"- Source: {price_data['source']}")
            if 'confidence' in price_data:
                print(f"- Confidence: {price_data['confidence']:.1f}%")
        else:
            print(f"- No price data found for {item}")
    
    # Report results
    print(f"\nGathered market data for {len(results)} out of {len(test_items)} items")
    print("Data is cached and ready for analysis")
    
    # Save raw results for reference
    with open("cache/gathered_test_data.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Raw results saved to cache/gathered_test_data.json")
    
if __name__ == "__main__":
    main()
