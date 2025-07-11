#!/usr/bin/env python3
"""
Auction Analyzer - Finds optimal prices and good deals at auction
"""
import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple
import requests
from bs4 import BeautifulSoup
import time
import random
from concurrent.futures import ThreadPoolExecutor
import json
import os

class AuctionAnalyzer:
    def __init__(self, data_file: str):
        """Initialize the analyzer with data file path"""
        self.data_file = data_file
        self.df = None
        self.market_prices = {}
        
        # Create cache directory if it doesn't exist
        os.makedirs("cache", exist_ok=True)
        self.cache_file = "cache/market_prices.json"
        
        # Load cache if it exists
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.market_prices = json.load(f)
        
    def parse_data(self) -> pd.DataFrame:
        """Parse the auction data file into a structured DataFrame"""
        items = []
        
        with open(self.data_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line == "INTERMISSION":
                    continue
                    
                # Extract item number and description
                match = re.match(r'^(\d+)\s+(.*?)(?:\s+Retail\s+\$([0-9,]+))?(?:\s+Starting\s+Bid\s+\$([0-9,]+))?$', line)
                if match:
                    item_num, description, retail, starting_bid = match.groups()
                    
                    # Clean the values
                    retail = int(retail.replace(',', '')) if retail else None
                    starting_bid = int(starting_bid.replace(',', '')) if starting_bid else None
                    
                    items.append({
                        'item_number': int(item_num),
                        'description': description,
                        'retail_price': retail,
                        'starting_bid': starting_bid
                    })
                
        self.df = pd.DataFrame(items)
        return self.df
    
    def search_online_price(self, item_description: str) -> float:
        """
        Search online for typical market price of an item
        This is a simplified implementation - in a real system, this would use
        more advanced scraping or API integration with Reverb, eBay, etc.
        """
        # Check cache first
        if item_description in self.market_prices:
            return self.market_prices[item_description]
            
        # For demo purposes, we'll use a formula based on retail price with some randomness
        # In a real implementation, this would be replaced with actual web scraping
        if self.df is not None:
            item_row = self.df[self.df['description'] == item_description]
            if not item_row.empty:
                retail = item_row['retail_price'].values[0]
                # Add some randomness to simulate different market conditions
                market_multiplier = random.uniform(0.85, 1.1)
                market_price = round(retail * market_multiplier)
                
                # Cache the result
                self.market_prices[item_description] = market_price
                with open(self.cache_file, 'w') as f:
                    json.dump(self.market_prices, f)
                    
                return market_price
        
        return None
    
    def get_all_market_prices(self) -> None:
        """Get market prices for all items using multithreading"""
        if self.df is None:
            self.parse_data()
            
        def get_price(row):
            time.sleep(0.1)  # To avoid overwhelming API/websites in a real implementation
            return self.search_online_price(row['description'])
            
        print("Fetching market prices... (simulated for this demo)")
        with ThreadPoolExecutor(max_workers=5) as executor:
            market_prices = list(executor.map(get_price, self.df.to_dict('records')))
            
        self.df['market_price'] = market_prices
        
    def calculate_optimal_price(self) -> pd.DataFrame:
        """Calculate the optimal price for each item"""
        if 'market_price' not in self.df.columns:
            self.get_all_market_prices()
            
        # Calculate various price metrics
        self.df['bid_to_retail_ratio'] = self.df['starting_bid'] / self.df['retail_price']
        self.df['market_to_retail_ratio'] = self.df['market_price'] / self.df['retail_price']
        
        # Calculate optimal price based on various factors
        # For simplicity, we'll use a weighted average of market and retail price
        self.df['optimal_price'] = (0.6 * self.df['market_price'] + 0.4 * self.df['retail_price']).round()
        
        # Calculate deal score: how good of a deal is the starting bid compared to optimal price
        self.df['deal_score'] = ((self.df['optimal_price'] - self.df['starting_bid']) / self.df['optimal_price'] * 100).round(1)
        
        # Classify deals
        def classify_deal(score):
            if score <= 0:
                return "Overpriced"
            elif score < 30:
                return "Fair"
            elif score < 50:
                return "Good Deal"
            else:
                return "Great Deal"
                
        self.df['deal_rating'] = self.df['deal_score'].apply(classify_deal)
        
        return self.df
    
    def get_top_deals(self, n: int = 10) -> pd.DataFrame:
        """Get the top N deals sorted by deal score"""
        if 'deal_score' not in self.df.columns:
            self.calculate_optimal_price()
            
        return self.df.sort_values('deal_score', ascending=False).head(n)
    
    def get_all_deals(self) -> Dict[str, pd.DataFrame]:
        """Get all deals categorized by rating"""
        if 'deal_rating' not in self.df.columns:
            self.calculate_optimal_price()
            
        result = {}
        for rating in ['Great Deal', 'Good Deal', 'Fair', 'Overpriced']:
            result[rating] = self.df[self.df['deal_rating'] == rating].sort_values('deal_score', ascending=False)
            
        return result
    
    def export_results(self, output_file: str = "auction_analysis.csv") -> None:
        """Export results to CSV"""
        if 'deal_rating' not in self.df.columns:
            self.calculate_optimal_price()
            
        self.df.to_csv(output_file, index=False)
        print(f"Results exported to {output_file}")
        
    def print_summary(self) -> None:
        """Print summary of analysis"""
        if 'deal_rating' not in self.df.columns:
            self.calculate_optimal_price()
            
        total = len(self.df)
        deal_counts = self.df['deal_rating'].value_counts()
        
        print("\n===== AUCTION ANALYSIS SUMMARY =====")
        print(f"Total items analyzed: {total}")
        print("\nDeal breakdown:")
        for rating, count in deal_counts.items():
            percent = round(count / total * 100, 1)
            print(f"  {rating}: {count} items ({percent}%)")
            
        print("\nTop 5 deals:")
        top_deals = self.get_top_deals(5)
        for _, row in top_deals.iterrows():
            print(f"  #{row['item_number']}: {row['description']} - {row['deal_rating']} (Score: {row['deal_score']})")
            print(f"    Starting bid: ${row['starting_bid']} | Optimal price: ${row['optimal_price']} | Retail: ${row['retail_price']}")
            
        print("\nWorst 5 deals:")
        worst_deals = self.df.sort_values('deal_score').head(5)
        for _, row in worst_deals.iterrows():
            print(f"  #{row['item_number']}: {row['description']} - {row['deal_rating']} (Score: {row['deal_score']})")
            print(f"    Starting bid: ${row['starting_bid']} | Optimal price: ${row['optimal_price']} | Retail: ${row['retail_price']}")
            

if __name__ == "__main__":
    analyzer = AuctionAnalyzer("data.txt")
    analyzer.parse_data()
    analyzer.calculate_optimal_price()
    analyzer.print_summary()
    analyzer.export_results()
