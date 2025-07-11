#!/usr/bin/env python3
"""
DuckDB Auction Analyzer - Uses DuckDB for efficient analysis of auction data
"""
import pandas as pd
import duckdb
import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
from tabulate import tabulate
from typing import Dict, List, Tuple, Optional
from market_scraper import MarketScraper
import re


class DuckDBAnalyzer:
    def __init__(self, data_file: str):
        """Initialize the analyzer with data file path"""
        self.data_file = data_file
        self.con = duckdb.connect(':memory:')
        self.market_scraper = MarketScraper()
        self.tables_created = False
        
    def parse_data(self) -> None:
        """Parse auction data and load into DuckDB"""
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
                        'starting_bid': starting_bid,
                        'category': self._categorize_item(description)
                    })
        
        # Create DuckDB table from items
        df = pd.DataFrame(items)
        self.con.execute("CREATE TABLE IF NOT EXISTS items AS SELECT * FROM df")
        self.tables_created = True
        
    def _categorize_item(self, description: str) -> str:
        """Categorize item based on description"""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['guitar', 'stratocaster', 'les paul', 'telecaster']):
            if 'acoustic' in description_lower:
                return 'Acoustic Guitar'
            elif 'bass' in description_lower:
                return 'Bass Guitar'
            else:
                return 'Electric Guitar'
        elif any(word in description_lower for word in ['amp', 'amplifier']):
            return 'Amplifier'
        elif any(word in description_lower for word in ['pedal', 'effect', 'delay', 'reverb', 'overdrive']):
            return 'Effect Pedal'
        elif any(word in description_lower for word in ['ukulele']):
            return 'Ukulele'
        elif any(word in description_lower for word in ['banjo']):
            return 'Banjo'
        elif any(word in description_lower for word in ['mandolin']):
            return 'Mandolin'
        else:
            return 'Other'
            
    def fetch_market_prices(self) -> None:
        """Fetch market prices for all items and update DuckDB table"""
        if not self.tables_created:
            self.parse_data()
            
        # Get all items from DuckDB
        items_df = self.con.execute("SELECT item_number, description FROM items").fetchdf()
        
        # Fetch market prices
        print("Fetching market prices for all items... This might take a while")
        market_data = []
        
        for _, row in items_df.iterrows():
            item_num = row['item_number']
            description = row['description']
            
            # Get market prices from scraper
            prices = self.market_scraper.get_market_price(description)
            
            market_data.append({
                'item_number': item_num,
                'reverb_price': prices.get('reverb'),
                'ebay_price': prices.get('ebay'),
                'sweetwater_price': prices.get('sweetwater'),
                'market_price': prices.get('average')
            })
            
            print(f"Fetched prices for item #{item_num}")
            
        # Create market prices table in DuckDB
        market_df = pd.DataFrame(market_data)
        self.con.execute("CREATE TABLE IF NOT EXISTS market_prices AS SELECT * FROM market_df")
        
        # Join tables
        self.con.execute("""
            CREATE OR REPLACE VIEW item_analysis AS
            SELECT 
                i.item_number,
                i.description,
                i.category,
                i.retail_price,
                i.starting_bid,
                m.reverb_price,
                m.ebay_price, 
                m.sweetwater_price,
                m.market_price,
                CASE 
                    WHEN m.market_price IS NOT NULL THEN (0.6 * m.market_price + 0.4 * i.retail_price)
                    ELSE i.retail_price 
                END AS optimal_price,
                CASE 
                    WHEN m.market_price IS NOT NULL THEN (m.market_price / i.retail_price) * 100
                    ELSE 100 
                END AS market_to_retail_pct,
                (i.starting_bid / i.retail_price) * 100 AS bid_to_retail_pct
            FROM items i
            JOIN market_prices m ON i.item_number = m.item_number
        """)
        
    def calculate_deals(self) -> None:
        """Calculate deal scores and categories"""
        if not self.tables_created:
            self.parse_data()
            
        # Calculate deal score and categorize
        self.con.execute("""
            CREATE OR REPLACE VIEW deal_analysis AS
            SELECT 
                *,
                ROUND(((optimal_price - starting_bid) / optimal_price) * 100, 1) AS deal_score,
                CASE 
                    WHEN ((optimal_price - starting_bid) / optimal_price) * 100 <= 0 THEN 'Overpriced'
                    WHEN ((optimal_price - starting_bid) / optimal_price) * 100 < 30 THEN 'Fair Deal'
                    WHEN ((optimal_price - starting_bid) / optimal_price) * 100 < 50 THEN 'Good Deal'
                    ELSE 'Great Deal'
                END AS deal_rating,
                ROUND(starting_bid / optimal_price * 100, 1) AS value_percentage
            FROM item_analysis
            ORDER BY deal_score DESC
        """)
        
    def get_top_deals(self, n: int = 10) -> pd.DataFrame:
        """Get top N deals"""
        self.calculate_deals()
        return self.con.execute(f"""
            SELECT 
                item_number,
                description, 
                category,
                retail_price, 
                starting_bid,
                ROUND(market_price) AS market_price,
                ROUND(optimal_price) AS optimal_price,
                deal_score,
                deal_rating
            FROM deal_analysis
            ORDER BY deal_score DESC
            LIMIT {n}
        """).fetchdf()
        
    def get_deals_by_rating(self, rating: str) -> pd.DataFrame:
        """Get deals by rating category"""
        self.calculate_deals()
        return self.con.execute(f"""
            SELECT 
                item_number,
                description, 
                category,
                retail_price, 
                starting_bid,
                ROUND(market_price) AS market_price,
                ROUND(optimal_price) AS optimal_price,
                deal_score
            FROM deal_analysis
            WHERE deal_rating = '{rating}'
            ORDER BY deal_score DESC
        """).fetchdf()
        
    def get_deals_by_category(self, category: str) -> pd.DataFrame:
        """Get deals by item category"""
        self.calculate_deals()
        return self.con.execute(f"""
            SELECT 
                item_number,
                description, 
                category,
                retail_price, 
                starting_bid,
                ROUND(market_price) AS market_price,
                ROUND(optimal_price) AS optimal_price,
                deal_score,
                deal_rating
            FROM deal_analysis
            WHERE category = '{category}'
            ORDER BY deal_score DESC
        """).fetchdf()
        
    def export_results(self, output_dir: str = "results") -> None:
        """Export results to CSV files"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Export main analysis
        deals_df = self.con.execute("""
            SELECT * FROM deal_analysis
        """).fetchdf()
        
        deals_df.to_csv(os.path.join(output_dir, "auction_analysis.csv"), index=False)
        
        # Export by category
        categories = self.con.execute("""
            SELECT DISTINCT category FROM items
        """).fetchall()
        
        for (category,) in categories:
            cat_df = self.get_deals_by_category(category)
            cat_df.to_csv(os.path.join(output_dir, f"{category.lower().replace(' ', '_')}_deals.csv"), index=False)
            
        print(f"Results exported to {output_dir}/ directory")
            
    def create_visualizations(self, output_dir: str = "results") -> None:
        """Create visualizations of the auction data"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        sns.set_style('whitegrid')
        plt.rcParams['figure.figsize'] = (10, 6)
        
        # 1. Deal distribution by rating
        deal_counts = self.con.execute("""
            SELECT deal_rating, COUNT(*) as count 
            FROM deal_analysis 
            GROUP BY deal_rating 
            ORDER BY 
                CASE 
                    WHEN deal_rating = 'Great Deal' THEN 1
                    WHEN deal_rating = 'Good Deal' THEN 2 
                    WHEN deal_rating = 'Fair Deal' THEN 3
                    ELSE 4
                END
        """).fetchdf()
        
        plt.figure(figsize=(10, 6))
        sns.barplot(x='deal_rating', y='count', data=deal_counts, palette='viridis')
        plt.title('Distribution of Deals by Rating')
        plt.xlabel('Deal Rating')
        plt.ylabel('Count')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'deal_distribution.png'), dpi=300)
        
        # 2. Deal score distribution by category
        plt.figure(figsize=(12, 8))
        category_deals = self.con.execute("""
            SELECT category, deal_score
            FROM deal_analysis
        """).fetchdf()
        
        sns.boxplot(x='category', y='deal_score', data=category_deals, palette='Set3')
        plt.title('Deal Score Distribution by Category')
        plt.xlabel('Category')
        plt.ylabel('Deal Score (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'category_deal_scores.png'), dpi=300)
        
        # 3. Starting bid vs. optimal price scatter
        plt.figure(figsize=(10, 8))
        price_data = self.con.execute("""
            SELECT 
                starting_bid, 
                optimal_price,
                category,
                deal_rating
            FROM deal_analysis
        """).fetchdf()
        
        sns.scatterplot(
            x='starting_bid', 
            y='optimal_price', 
            hue='deal_rating', 
            style='category',
            s=100, 
            alpha=0.7, 
            data=price_data
        )
        
        # Add diagonal line representing equal prices
        max_val = max(price_data['starting_bid'].max(), price_data['optimal_price'].max())
        plt.plot([0, max_val], [0, max_val], 'r--', alpha=0.3)
        
        plt.title('Starting Bid vs. Optimal Price')
        plt.xlabel('Starting Bid ($)')
        plt.ylabel('Optimal Price ($)')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'bid_vs_optimal.png'), dpi=300)
        
        print(f"Visualizations saved to {output_dir}/ directory")
        
    def print_summary(self) -> None:
        """Print summary of auction analysis"""
        self.calculate_deals()
        
        # Overall stats
        stats = self.con.execute("""
            SELECT 
                COUNT(*) as total_items,
                ROUND(AVG(deal_score), 1) as avg_deal_score,
                ROUND(MIN(deal_score), 1) as min_deal_score,
                ROUND(MAX(deal_score), 1) as max_deal_score,
                ROUND(SUM(retail_price), 2) as total_retail_value,
                ROUND(SUM(starting_bid), 2) as total_starting_bids,
                ROUND(SUM(optimal_price - starting_bid), 2) as total_potential_savings
            FROM deal_analysis
        """).fetchone()
        
        # Deal breakdown
        deal_counts = self.con.execute("""
            SELECT 
                deal_rating, 
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM deal_analysis), 1) as percentage
            FROM deal_analysis 
            GROUP BY deal_rating
            ORDER BY 
                CASE 
                    WHEN deal_rating = 'Great Deal' THEN 1
                    WHEN deal_rating = 'Good Deal' THEN 2 
                    WHEN deal_rating = 'Fair Deal' THEN 3
                    ELSE 4
                END
        """).fetchdf()
        
        # Category breakdown
        category_counts = self.con.execute("""
            SELECT 
                category,
                COUNT(*) as count,
                ROUND(AVG(deal_score), 1) as avg_deal_score
            FROM deal_analysis
            GROUP BY category
            ORDER BY avg_deal_score DESC
        """).fetchdf()
        
        # Top 5 deals
        top_deals = self.get_top_deals(5)
        
        # Print summary
        print("\n===== AUCTION ANALYSIS SUMMARY =====\n")
        print(f"Total items analyzed: {stats[0]}")
        print(f"Average deal score: {stats[1]}%")
        print(f"Range of deal scores: {stats[2]}% to {stats[3]}%")
        print(f"Total retail value: ${stats[4]:,.2f}")
        print(f"Total starting bids: ${stats[5]:,.2f}")
        print(f"Total potential savings: ${stats[6]:,.2f}")
        
        print("\nDeal breakdown:")
        print(tabulate(deal_counts, headers='keys', tablefmt='pretty', showindex=False))
        
        print("\nCategory analysis:")
        print(tabulate(category_counts, headers='keys', tablefmt='pretty', showindex=False))
        
        print("\nTop 5 deals:")
        for _, row in top_deals.iterrows():
            print(f"  #{row['item_number']}: {row['description']} - {row['deal_rating']} (Score: {row['deal_score']})")
            print(f"    Starting bid: ${row['starting_bid']} | Optimal price: ${row['optimal_price']} | Retail: ${row['retail_price']}")
            
        # Worst 5 deals
        worst_deals = self.con.execute("""
            SELECT 
                item_number,
                description, 
                retail_price, 
                starting_bid,
                ROUND(optimal_price) AS optimal_price,
                deal_score,
                deal_rating
            FROM deal_analysis
            ORDER BY deal_score ASC
            LIMIT 5
        """).fetchdf()
        
        print("\nWorst 5 deals:")
        for _, row in worst_deals.iterrows():
            print(f"  #{row['item_number']}: {row['description']} - {row['deal_rating']} (Score: {row['deal_score']})")
            print(f"    Starting bid: ${row['starting_bid']} | Optimal price: ${row['optimal_price']} | Retail: ${row['retail_price']}")


if __name__ == "__main__":
    analyzer = DuckDBAnalyzer("data.txt")
    analyzer.parse_data()
    analyzer.fetch_market_prices()
    analyzer.calculate_deals()
    analyzer.print_summary()
    analyzer.export_results()
    analyzer.create_visualizations()
