#!/usr/bin/env python3
"""
Real Auction Data Analyzer

This script analyzes actual auction data by:
1. Fetching real-time market prices from eBay sold listings
2. Comparing auction prices to market values
3. Identifying deals, fair prices, and overpriced items
4. Calculating optimal bid prices for each item
"""
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from market_scraper import MarketScraper
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RealAuctionAnalyzer:
    """Analyze auction items against real market data"""
    
    def __init__(self, auction_file="data/auction_items.txt", cache_dir="cache", 
                 max_items=10, random_sample=False, refresh_market_data=False):
        """Initialize the analyzer with auction data file"""
        self.auction_file = auction_file
        self.cache_dir = cache_dir
        self.market_scraper = MarketScraper(cache_dir=cache_dir)
        self.max_items = max_items  # Maximum number of items to analyze
        self.random_sample = random_sample  # Whether to take a random sample
        self.refresh_market_data = refresh_market_data  # Whether to refresh market data
        
        # Set up output directories
        self.output_dir = os.path.join(cache_dir, "analysis")
        self.plot_dir = os.path.join(self.output_dir, "plots")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.plot_dir, exist_ok=True)
        
        # Create a timestamped output folder for this run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(self.output_dir, f"run_{timestamp}")
        os.makedirs(self.run_dir, exist_ok=True)
        os.makedirs(os.path.join(self.run_dir, "plots"), exist_ok=True)
        
        # Make sure the auction data directory exists
        data_dir = os.path.dirname(auction_file)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        # Deal scoring thresholds
        self.deal_threshold = float(os.getenv("DEAL_THRESHOLD", "0.85"))  # 15% below median is a deal
        self.overpriced_threshold = float(os.getenv("OVERPRICED_THRESHOLD", "1.15"))  # 15% above median is overpriced
        
        # Store results for CLI integration
        self.results_df = pd.DataFrame()
        self.items_df = pd.DataFrame()
        self.market_df = pd.DataFrame()
        
    def load_auction_data(self):
        """
        Load auction items from the data file
        If the file doesn't exist, create a sample file
        """
        if not os.path.exists(self.auction_file):
            print(f"Creating sample auction data file at {self.auction_file}")
            self._create_sample_auction_file()
        
        try:
            # Read auction data format: [Lot #] [Item Description] Retail $[amount] Starting Bid $[amount]
            items = []
            with open(self.auction_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line == 'INTERMISSION':
                        continue
                    
                    # Parse the real auction format
                    try:
                        # Extract retail price and starting bid using regex
                        import re
                        retail_match = re.search(r'Retail \$(\d+[,\d]*)', line)
                        bid_match = re.search(r'Starting Bid \$(\d+[,\d]*)', line)
                        
                        if retail_match and bid_match:
                            # Extract the item number and description
                            lot_num = line.split(' ')[0]
                            
                            # Get the description (everything between lot number and 'Retail')
                            description = line[len(lot_num):line.find('Retail')].strip()
                            
                            # Parse prices
                            retail_price = float(retail_match.group(1).replace(',', ''))
                            starting_bid = float(bid_match.group(1).replace(',', ''))
                            
                            items.append({
                                'lot': lot_num,
                                'description': description,
                                'retail_price': retail_price,
                                'starting_bid': starting_bid
                            })
                    except Exception as parsing_error:
                        print(f"Could not parse line: {line}")
                        print(f"Error: {parsing_error}")
            
            print(f"Loaded {len(items)} auction items")
            
            # Convert to DataFrame
            df = pd.DataFrame(items)
            
            # Take a subset if we have too many items
            if len(df) > self.max_items:
                if self.random_sample:
                    # Random sample
                    df = df.sample(n=self.max_items, random_state=42)
                    print(f"Randomly sampled {self.max_items} items for analysis")
                else:
                    # Take the first N items
                    df = df.head(self.max_items)
                    print(f"Taking first {self.max_items} items for analysis")
            
            return df
        except Exception as e:
            print(f"Error loading auction data: {str(e)}")
            return pd.DataFrame()
    
    def _create_sample_auction_file(self):
        """Create a sample auction data file if one doesn't exist"""
        sample_data = [
            "Fender Stratocaster American Professional II|$1599.99|$899.00",
            "Gibson Les Paul Standard 60s|$2799.00|$1599.00",
            "Boss DS-1 Distortion Pedal|$59.99|$29.99",
            "Shure SM58 Microphone|$99.00|$59.00",
            "Audio Technica AT2020 Condenser Mic|$149.00|$89.00",
            "Korg Minilogue Synthesizer|$529.99|$349.99",
            "Yamaha P-45 Digital Piano|$599.99|$399.99",
            "Akai MPK Mini MK3 MIDI Controller|$119.00|$79.00",
            "JBL 305P MKII Studio Monitor|$149.99|$89.99",
            "Behringer X32 Digital Mixer|$2999.99|$1899.99"
        ]
        
        os.makedirs(os.path.dirname(self.auction_file), exist_ok=True)
        with open(self.auction_file, 'w') as f:
            f.write("# Format: Item Description | Retail Price | Starting Bid\n")
            f.write("# Add your actual auction items below this line\n\n")
            f.write("\n".join(sample_data))
    
    def add_market_prices(self, items_df, refresh_cache=False):
        """Add market price data to each auction item"""
        # Make a copy to avoid pandas warnings
        items_df = items_df.copy()
        
        # Add columns for market data
        items_df['market_price'] = np.nan
        items_df['market_median'] = np.nan
        items_df['confidence'] = np.nan
        items_df['source'] = ''
        items_df['listing_count'] = 0
        items_df['condition_counts'] = None
        
        # Process each item
        for idx, row in items_df.iterrows():
            print(f"\nAnalyzing item {idx+1}/{len(items_df)}: {row['description']}")
            
            print(f"\n=> Fetching market price for: {row['description']}")
            price_data = self.market_scraper.get_market_price(row['description'], refresh_cache=refresh_cache)
            
            if price_data:
                # For eBay scraped data, the structure is different
                if price_data.get('source') == 'ebay_scraped':
                    # Direct access to the eBay scraped data format
                    items_df.at[idx, 'market_price'] = price_data.get('average_price', 0)
                    items_df.at[idx, 'market_median'] = price_data.get('median_price', 0)
                    items_df.at[idx, 'confidence'] = price_data.get('confidence_level', 0)
                    items_df.at[idx, 'source'] = price_data.get('source', 'ebay_scraped')
                    items_df.at[idx, 'listing_count'] = price_data.get('count', 0)
                    items_df.at[idx, 'condition_counts'] = str(price_data.get('condition_counts', {}))
                    
                    # Print some details about this item
                    print(f"- Found {price_data.get('count', 0)} eBay listings")
                    print(f"- Average price: ${price_data.get('average_price', 0):.2f}")
                    print(f"- Median price: ${price_data.get('median_price', 0):.2f}")
                    print(f"- Confidence: {price_data.get('confidence_level', 0):.0f}%")
                else:
                    # For eBay simulation or other sources
                    market_price = 0
                    confidence = 0
                    source = 'unknown'
                    
                    # Try to extract price data based on different possible structures
                    if 'price' in price_data:
                        market_price = price_data.get('price', 0)
                    elif 'average_price' in price_data:
                        market_price = price_data.get('average_price', 0)
                    
                    if 'confidence' in price_data:
                        confidence = price_data.get('confidence', 0)
                    elif 'confidence_level' in price_data:
                        confidence = price_data.get('confidence_level', 0)
                    
                    if 'source' in price_data:
                        source = price_data.get('source', 'unknown')
                        
                    # Update DataFrame with what we found
                    items_df.at[idx, 'market_price'] = market_price
                    items_df.at[idx, 'market_median'] = market_price  # Use price as median
                    items_df.at[idx, 'confidence'] = confidence
                    items_df.at[idx, 'source'] = source
                    
                    # Special case: if we have eBay simulation data, try to extract more
                    if source == 'ebay_simulation' and 'listings' in price_data:
                        listings = price_data.get('listings', [])
                        if listings:
                            prices = [item.get('price', 0) for item in listings if 'price' in item]
                            if prices:
                                items_df.at[idx, 'listing_count'] = len(prices)
                                items_df.at[idx, 'market_price'] = sum(prices) / len(prices) if prices else 0
                                print(f"- Found {len(listings)} simulated listings")
                                print(f"- Average price: ${items_df.at[idx, 'market_price']:.2f}")
                
                # Print summary information
                price_to_display = items_df.at[idx, 'market_price']
                confidence_to_display = items_df.at[idx, 'confidence']
                print(f"- Market price: ${price_to_display:.2f} (confidence: {confidence_to_display:.0f}%)")
                
                # This print statement is now handled in the structured data processing above
            else:
                print(f"- No market data found for {row['description']}")
        
        # Fill NaN values in market_median with market_price (avoid inplace warning)
        market_median = items_df['market_median']
        items_df['market_median'] = market_median.fillna(items_df['market_price'])
        
        # Store the data for later processing
        self.market_df = items_df.copy()
        
        return items_df
    
    def fetch_market_prices(self):
        """Fetch market prices for auction items - CLI compatibility method"""
        if not hasattr(self, 'items_df') or self.items_df.empty:
            self.items_df = self.load_auction_data()
            
        if self.items_df.empty:
            print("No auction items to analyze")
            return pd.DataFrame()
            
        # Add market prices to items
        self.market_df = self.add_market_prices(self.items_df, refresh_cache=self.refresh_market_data)
        return self.market_df
        
    def analyze_deals(self, items_df=None):
        """Analyze which items are deals, fair priced, or overpriced"""
        # Support being called without parameters for CLI compatibility
        if items_df is None:
            if hasattr(self, 'market_df') and not self.market_df.empty:
                items_df = self.market_df
            else:
                print("No market data available. Run fetch_market_prices() first.")
                return pd.DataFrame()
                
        if items_df.empty:
            return items_df
            
        # Calculate deal score (lower is better deal)
        # A score of 1.0 means it's at the fair market price
        items_df['deal_score'] = items_df['starting_bid'] / items_df['market_median']
        
        # Calculate optimal bid price
        # Base optimal price on median, but adjust for retail and confidence
        items_df['optimal_bid'] = items_df.apply(
            lambda row: self._calculate_optimal_price(
                row['market_median'], 
                row['retail_price'],
                row['confidence']
            ), 
            axis=1
        )
        
        # Calculate savings percentage
        items_df['savings_pct'] = ((items_df['market_median'] - items_df['starting_bid']) / items_df['market_median']) * 100
        
        # Calculate premium percentage for overpriced items
        items_df['premium_pct'] = ((items_df['starting_bid'] - items_df['market_median']) / items_df['market_median']) * 100
        
        # Categorize items by deal quality
        items_df['price_category'] = 'fair_price'  # Default
        items_df.loc[items_df['deal_score'] <= self.deal_threshold, 'price_category'] = 'good_deal'
        items_df.loc[items_df['deal_score'] >= self.overpriced_threshold, 'price_category'] = 'overpriced'
        
        # Update our results dataframe for CLI access
        self.results_df = items_df.copy()
        
        # For compatibility with CLI integration
        self.results_df['deal_category'] = self.results_df['price_category'] 
        self.results_df['item_number'] = self.results_df['lot']
        self.results_df['market_price'] = self.results_df['market_median']
        
        # Add category field if not present for compatibility with category command
        if 'category' not in self.results_df.columns:
            # Extract categories based on instrument keywords in the descriptions
            def extract_category(description):
                description = description.lower()
                if any(word in description for word in ['guitar', 'stratocaster', 'les paul', 'sg', 'acoustic']):
                    if 'electric' in description or any(word in description for word in ['stratocaster', 'sg', 'les paul', 'polara']):
                        return 'Electric Guitar'
                    elif 'acoustic' in description or 'parlor' in description:
                        return 'Acoustic Guitar'
                    else:
                        return 'Guitar'
                elif any(word in description for word in ['bass', 'jazz bass']):
                    return 'Bass Guitar'
                elif any(word in description for word in ['ukulele', 'uke']):
                    return 'Ukulele'
                elif any(word in description for word in ['mandolin']):
                    return 'Mandolin'
                elif any(word in description for word in ['conga', 'percussion', 'drum']):
                    return 'Percussion'
                elif any(word in description for word in ['pedal', 'delay', 'electronics']):
                    return 'Effects Pedal'
                elif any(word in description for word in ['resonator']):
                    return 'Resonator'
                else:
                    return 'Other Instrument'
            
            self.results_df['category'] = self.results_df['description'].apply(extract_category)
            
        return items_df
        
    def _calculate_optimal_price(self, market_price, retail_price, confidence):
        """
        Calculate optimal bid price based on market data and confidence
        Weighted calculation that factors in both market and retail price
        """
        # Base discount from median based on auction dynamics (typically 10-20%)
        base_auction_discount = 0.85  # 15% below market median is a good target
        
        # Weight market price more heavily when confidence is high
        if confidence >= 80:
            # With high confidence, weigh market price 70%, retail 30%
            market_weight = 0.7
            # With medium confidence, more balanced weighting
            market_weight = 0.6
        else:
            # With low confidence, weigh retail price more heavily
            market_weight = 0.4
            
        retail_weight = 1 - market_weight
        
        # Calculate weighted optimal price
        weighted_price = (market_price * market_weight) + (retail_price * retail_weight)
        
        # Apply auction discount
        optimal_price = weighted_price * base_auction_discount
        
        return optimal_price
    
    def generate_visualizations(self, items_df):
        """Generate visualizations of the deal analysis"""
        if items_df.empty:
            return
        
        # Set the style
        sns.set_style("whitegrid")
        plt.rcParams.update({'font.size': 10})  # Smaller font for labels
        
        # Use shortened descriptions for cleaner charts
        items_df['short_desc'] = items_df['description'].apply(
            lambda x: x[:30] + '...' if len(x) > 30 else x
        )
        
        # 1. Deal Score Distribution
        plt.figure(figsize=(14, 8))
        ax = sns.barplot(
            x='short_desc', 
            y='deal_score', 
            data=items_df,
            hue='price_category', 
            palette={'good_deal': 'green', 'fair_price': 'blue', 'overpriced': 'red'}
        )
        plt.axhline(y=1.0, color='black', linestyle='--', alpha=0.7, label='Fair Price Line')
        plt.axhline(y=self.deal_threshold, color='green', linestyle=':', alpha=0.7, label=f'Deal Threshold ({self.deal_threshold})')
        plt.axhline(y=self.overpriced_threshold, color='red', linestyle=':', alpha=0.7, label=f'Overpriced Threshold ({self.overpriced_threshold})')
        plt.xticks(rotation=45, ha='right')
        plt.title('Deal Score by Item (Lower is Better Deal)')
        plt.ylabel('Deal Score (Starting Bid / Market Median)')
        plt.xlabel('Item')
        plt.legend()
        plt.tight_layout()
        
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'deal_scores.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'deal_scores.png'), dpi=300)
        
        # 2. Price Comparison (Market vs Starting Bid vs Optimal)
        price_data = pd.DataFrame({
            'Item': items_df['short_desc'],
            'Starting Bid': items_df['starting_bid'],
            'Market Median': items_df['market_median'],
            'Optimal Bid': items_df['optimal_bid']
        })
        price_data_melted = price_data.melt(id_vars=['Item'], var_name='Price Type', value_name='Price')
        
        plt.figure(figsize=(14, 8))
        sns.barplot(x='Item', y='Price', hue='Price Type', data=price_data_melted)
        plt.xticks(rotation=45, ha='right')
        plt.title('Price Comparison: Market vs Starting Bid vs Optimal')
        plt.ylabel('Price ($)')
        plt.xlabel('Item')
        plt.legend(title='Price Type')
        plt.tight_layout()
        
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'price_comparison.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'price_comparison.png'), dpi=300)
        
        # 3. Savings Percentage
        plt.figure(figsize=(14, 8))
        # Create a fixed color map
        colors = ['green' if pct > 0 else 'red' for pct in items_df['savings_pct']]
        
        # Use a more reliable approach for barplot
        ax = plt.bar(
            x=range(len(items_df)),
            height=items_df['savings_pct'],
            color=colors
        )
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.7)
        
        # Add value labels on bars
        for i, bar in enumerate(ax):
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width()/2., 
                height + 1 if height > 0 else height - 3, 
                f"{items_df['savings_pct'].iloc[i]:.1f}%", 
                ha='center', va='bottom' if height > 0 else 'top',
                color='black'
            )
        
        plt.xticks(range(len(items_df)), items_df['short_desc'], rotation=45, ha='right')
        plt.title('Savings Percentage Compared to Market Value')
        plt.ylabel('Savings %')
        plt.xlabel('Item')
        plt.tight_layout()
        
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'savings_percentage.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'savings_percentage.png'), dpi=300)
        
        plt.close('all')
    
    def save_analysis_results(self, items_df):
        """Save analysis results to CSV"""
        if items_df.empty:
            return
        
        # Order results by deal score (best deals first)
        # Make sure to handle NaN values before sorting
        report_df = items_df.copy()
        report_df['deal_score'] = report_df['deal_score'].fillna(float('inf'))  # NaN becomes worst deal
        report_df = report_df.sort_values('deal_score').copy()
        
        # Format percentage columns
        report_df['savings_pct'] = report_df['savings_pct'].map(lambda x: f"{x:.1f}%")
        report_df['confidence'] = report_df['confidence'].map(lambda x: f"{x:.0f}%" if not pd.isna(x) else "0%")
        
        # Save to both locations
        output_file = os.path.join(self.output_dir, "auction_analysis.csv")
        report_df.to_csv(output_file, index=False)
        
        # Save to run-specific directory
        run_output_file = os.path.join(self.run_dir, "auction_analysis.csv")
        report_df.to_csv(run_output_file, index=False)
        
        print(f"Saved analysis results to:\n- {output_file}\n- {run_output_file}")
        
        # Return top results for display
        return report_df
    
    def create_visualizations(self, output_dir=None):
        """Generate visualizations of the deal analysis for CLI integration"""
        if not hasattr(self, 'results_df') or self.results_df.empty:
            print("No analysis results available. Run analyze_deals() first.")
            return
        
        # Use specified output directory or default
        vis_dir = output_dir if output_dir else self.run_dir
        os.makedirs(os.path.join(vis_dir, "plots"), exist_ok=True)
        
        # Generate the standard visualizations
        self.generate_visualizations(self.results_df)
            
    def generate_visualizations(self, items_df):
        """Generate visualizations of the deal analysis"""
        if items_df.empty:
            return
        
        # Set the style
        sns.set_style("whitegrid")
        plt.rcParams.update({'font.size': 10})  # Smaller font for labels
            
        # Use shortened descriptions for cleaner charts
        items_df['short_desc'] = items_df['description'].apply(
            lambda x: x[:30] + '...' if len(x) > 30 else x
        )
            
        # 1. Deal Score Distribution
        plt.figure(figsize=(14, 8))
        ax = sns.barplot(
            x='short_desc', 
            y='deal_score', 
            data=items_df,
            hue='price_category', 
            palette={'good_deal': 'green', 'fair_price': 'blue', 'overpriced': 'red'}
        )
        plt.axhline(y=1.0, color='black', linestyle='--', alpha=0.7, label='Fair Price Line')
        plt.axhline(y=self.deal_threshold, color='green', linestyle=':', alpha=0.7, label=f'Deal Threshold ({self.deal_threshold})')
        plt.axhline(y=self.overpriced_threshold, color='red', linestyle=':', alpha=0.7, label=f'Overpriced Threshold ({self.overpriced_threshold})')
        plt.xticks(rotation=45, ha='right')
        plt.title('Deal Score by Item (Lower is Better Deal)')
        plt.ylabel('Deal Score (Starting Bid / Market Median)')
        plt.xlabel('Item')
        plt.legend()
        plt.tight_layout()
            
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'deal_scores.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'deal_scores.png'), dpi=300)
            
        # 2. Price Comparison (Market vs Starting Bid vs Optimal)
        price_data = pd.DataFrame({
            'Item': items_df['short_desc'],
            'Starting Bid': items_df['starting_bid'],
            'Market Median': items_df['market_median'],
            'Optimal Bid': items_df['optimal_bid']
        })
        price_data_melted = price_data.melt(id_vars=['Item'], var_name='Price Type', value_name='Price')
            
        plt.figure(figsize=(14, 8))
        sns.barplot(x='Item', y='Price', hue='Price Type', data=price_data_melted)
        plt.xticks(rotation=45, ha='right')
        plt.title('Price Comparison: Market vs Starting Bid vs Optimal')
        plt.ylabel('Price ($)')
        plt.xlabel('Item')
        plt.legend(title='Price Type')
        plt.tight_layout()
            
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'price_comparison.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'price_comparison.png'), dpi=300)
            
        # 3. Savings Percentage
        plt.figure(figsize=(14, 8))
        # Create a fixed color map
        colors = ['green' if pct > 0 else 'red' for pct in items_df['savings_pct']]
            
        # Use a more reliable approach for barplot
        ax = plt.bar(
            x=range(len(items_df)),
            height=items_df['savings_pct'],
            color=colors
        )
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.7)
            
        # Add value labels on bars
        for i, bar in enumerate(ax):
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width()/2., 
                height + 1 if height > 0 else height - 3, 
                f"{items_df['savings_pct'].iloc[i]:.1f}%", 
                ha='center', va='bottom' if height > 0 else 'top',
                color='black'
            )
        
        plt.xticks(range(len(items_df)), items_df['short_desc'], rotation=45, ha='right')
        plt.title('Savings Percentage Compared to Market Value')
        plt.ylabel('Savings %')
        plt.xlabel('Item')
        plt.tight_layout()
            
        # Save to both locations
        plt.savefig(os.path.join(self.plot_dir, 'savings_percentage.png'), dpi=300)
        plt.savefig(os.path.join(self.run_dir, 'plots', 'savings_percentage.png'), dpi=300)
        
    plt.close('all')
    
    def save_analysis_results(self, items_df):
        """Save analysis results to CSV"""
        if items_df.empty:
            return
        
        # Order results by deal score (best deals first)
        # Make sure to handle NaN values before sorting
        report_df = items_df.copy()
        report_df['deal_score'] = report_df['deal_score'].fillna(float('inf'))  # NaN becomes worst deal
        report_df = report_df.sort_values('deal_score').copy()
            
        # Format percentage columns
        report_df['savings_pct'] = report_df['savings_pct'].map(lambda x: f"{x:.1f}%")
        report_df['confidence'] = report_df['confidence'].map(lambda x: f"{x:.0f}%" if not pd.isna(x) else "0%")
            
        # Save to both locations
        output_file = os.path.join(self.output_dir, "auction_analysis.csv")
        report_df.to_csv(output_file, index=False)
            
        # Save to run-specific directory
        run_output_file = os.path.join(self.run_dir, "auction_analysis.csv")
        report_df.to_csv(run_output_file, index=False)
            
        print(f"Saved analysis results to:\n- {output_file}\n- {run_output_file}")
            
        # Return top results for display
        return report_df
    
    def run_analysis(self):
        """Run the full auction analysis pipeline"""
        # Load auction data
        items_df = self.load_auction_data()
        if items_df.empty:
            print("No auction items loaded. Exiting.")
            return None
        
        # Add market price data
        items_with_prices = self.add_market_prices(items_df, refresh_cache=self.refresh_market_data)
            
        # Calculate deal scores
        items_analyzed = self.analyze_deals(items_with_prices)
            
        # Generate visualizations
        self.generate_visualizations(items_analyzed)
            
        # Save results to CSV
        self.save_analysis_results(items_analyzed)
            
        return items_analyzed

    def print_summary(self):
        """Print a summary of the analysis results for CLI integration"""
        if not hasattr(self, 'results_df') or self.results_df.empty:
            print("No analysis results available. Run analyze_deals() first.")
            return
                
        # Count deals, overpriced items, and fair prices
        good_deals = len(self.results_df[self.results_df['deal_category'] == 'good_deal'])
        overpriced = len(self.results_df[self.results_df['deal_category'] == 'overpriced'])
        fair_price = len(self.results_df[self.results_df['deal_category'] == 'fair_price'])
        total = len(self.results_df)
        
        if total == 0:
            print("No items to analyze")
            return
            
        # Calculate average savings percentage for good deals
        if good_deals > 0:
            avg_savings = self.results_df[self.results_df['deal_category'] == 'good_deal']['savings_pct'].mean()
        else:
            avg_savings = 0
                
        # Print the summary
        print("\n==================================================")
        print("AUCTION ANALYSIS SUMMARY")
        print("==================================================")
        print(f"Total items analyzed: {total}")
        print(f"✅ Good deals: {good_deals} items ({good_deals/total*100:.1f}%)")
        print(f"ℹ️ Fair prices: {fair_price} items ({fair_price/total*100:.1f}%)")
        print(f"⚠️ Overpriced: {overpriced} items ({overpriced/total*100:.1f}%)")
            
        if good_deals > 0:
            print(f"\nAverage savings on good deals: {avg_savings:.1f}%")
                
            # Show top 5 best deals
            best_deals = self.results_df[self.results_df['deal_category'] == 'good_deal'].sort_values('savings_pct', ascending=False).head(5)
                
            print("\n==================================================")
            print("TOP BEST DEALS")
            print("==================================================")
            for _, deal in best_deals.iterrows():
                print(f"Lot {deal['item_number']}: {deal['description']}")
                print(f"  Starting Bid: ${deal['starting_bid']:.2f}")
                print(f"  Market Value: ${deal['market_price']:.2f}")
                print(f"  Optimal Bid:  ${deal['optimal_bid']:.2f}")
                print(f"  Savings: {deal['savings_pct']:.1f}%")
                print("----------------------------------------")
            
        if overpriced > 0:
            # Show top 5 most overpriced items
            worst_deals = self.results_df[self.results_df['deal_category'] == 'overpriced'].sort_values('premium_pct', ascending=False).head(5)
                
            print("\n==================================================")
            print("MOST OVERPRICED ITEMS")
            print("==================================================")
            for _, deal in worst_deals.iterrows():
                print(f"Lot {deal['item_number']}: {deal['description']}")
                print(f"  Starting Bid: ${deal['starting_bid']:.2f}")
                print(f"  Market Value: ${deal['market_price']:.2f}")
                print(f"  Premium: {deal['premium_pct']:.1f}% above market")
                print("----------------------------------------")
            
        print("\nResults saved to:")
        print(f"- {os.path.join(self.output_dir, 'auction_analysis.csv')}")
        print(f"- {os.path.join(self.run_dir, 'auction_analysis.csv')}") 

# This duplicate definition has been removed

def main():
    """Main function to run the auction analyzer"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Auction Item Analysis Tool')
    parser.add_argument('--max-items', type=int, default=15, help='Maximum number of items to analyze')
    parser.add_argument('--random', action='store_true', help='Use random sample instead of first N items')
    parser.add_argument('--refresh', action='store_true', help='Refresh market data')
    args = parser.parse_args()
    
    print(f"\n{'='*50}")
    print(f"AUCTION ANALYZER")
    print(f"{'='*50}")
    print(f"Max items: {args.max_items}")
    print(f"Sample mode: {'Random sample' if args.random else 'First N items'}")
    print(f"Refresh market data: {'Yes' if args.refresh else 'No'}")
    print(f"{'='*50}\n")
    
    # Create analyzer with command line options
    analyzer = RealAuctionAnalyzer(
        auction_file="data/auction_items.txt",
        max_items=args.max_items,
        sample_randomly=args.random,
        refresh_market_data=args.refresh
    )
    
    results = analyzer.run_analysis()
    
    if results is not None:
        # Display summary of findings
        deal_counts = results['price_category'].value_counts()
        print("\n" + "=" * 50)
        print("AUCTION ANALYSIS SUMMARY")
        print("=" * 50)
        print(f"Total items analyzed: {len(results)}")
        
        # Print deal category counts
        for category, count in deal_counts.items():
            if category == 'good_deal':
                print(f"✅ {category}: {count} items")
            elif category == 'overpriced':
                print(f"⚠️ {category}: {count} items")
            else:
                print(f"ℹ️ {category}: {count} items")
        
        # Show top deals
        good_deals = results[results['price_category'] == 'good_deal']
        if not good_deals.empty:
            print("\n" + "=" * 50)
            print("TOP BEST DEALS")
            print("=" * 50)
            for idx, row in good_deals.head(5).iterrows():
                print(f"Lot {row['lot']}: {row['description']}")
                print(f"  Starting Bid: ${row['starting_bid']:.2f}")
                print(f"  Market Value: ${row['market_median']:.2f}")
                print(f"  Optimal Bid:  ${row['optimal_bid']:.2f}")
                # Format the savings percentage nicely
                if isinstance(row['savings_pct'], str) and '%' in row['savings_pct']:
                    savings = row['savings_pct']
                else:
                    savings = f"{float(row['savings_pct']):.1f}%"
                print(f"  Savings: {savings}")
                print(f"  Source: {row['source']}")
                print("-" * 40)
        
        # Show overpriced items
        overpriced = results[results['price_category'] == 'overpriced']
        if not overpriced.empty:
            print("\n" + "=" * 50)
            print("OVERPRICED ITEMS")
            print("=" * 50)
            for idx, row in overpriced.head(3).iterrows():
                print(f"Lot {row['lot']}: {row['description']}")
                print(f"  Starting Bid: ${row['starting_bid']:.2f}")
                print(f"  Market Value: ${row['market_median']:.2f}")
                # Handle the savings percentage correctly (could be float or string)
                if isinstance(row['savings_pct'], str) and '%' in row['savings_pct']:
                    premium = abs(float(row['savings_pct'].replace('%', '')))
                else:
                    premium = abs(float(row['savings_pct']))
                print(f"  Premium: {premium:.1f}% above market")
                print("-" * 40)
        
        # Show output paths
        print("\n" + "=" * 50)
        print("OUTPUT FILES")
        print("=" * 50)
        print(f"Analysis report: {os.path.join(analyzer.run_dir, 'auction_analysis.csv')}")
        print(f"Visualizations: {os.path.join(analyzer.run_dir, 'plots')}")
        print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
