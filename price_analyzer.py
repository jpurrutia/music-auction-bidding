#!/usr/bin/env python3
"""
Price Analyzer for Music Auction Bidding

This script performs exploratory data analysis (EDA) on price data gathered 
from multiple sources to identify deals and optimal pricing for auctions.
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

class PriceAnalyzer:
    """Analyzes market prices and identifies deals"""
    
    def __init__(self, cache_dir="cache"):
        """Initialize the price analyzer"""
        self.cache_dir = cache_dir
        self.market_scraper = MarketScraper(cache_dir=cache_dir)
        
        # Set up output directories
        self.output_dir = os.path.join(cache_dir, "analysis")
        self.plot_dir = os.path.join(self.output_dir, "plots")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.plot_dir, exist_ok=True)
        
        # Default thresholds for deal analysis
        self.deal_threshold = float(os.getenv("DEAL_THRESHOLD", "0.85"))  # 15% below median is a deal
        self.overpriced_threshold = float(os.getenv("OVERPRICED_THRESHOLD", "1.15"))  # 15% above median is overpriced
    
    def load_price_data(self):
        """Load cached price data into a pandas DataFrame for analysis"""
        # Get raw price cache
        price_cache = self.market_scraper.price_cache
        
        # Convert to DataFrame-friendly structure
        data_rows = []
        
        for description, data in price_cache.items():
            # Extract basic information
            if not isinstance(data, dict) or "price" not in data:
                continue
            
            row = {
                "item_description": description,
                "avg_price": data.get("price", 0),
                "timestamp": data.get("timestamp", ""),
                "confidence": data.get("confidence", 0),
                "source": data.get("source", "unknown"),
                "count": 0
            }
            
            # Extract source-specific data
            if "ebay_scraped" in data:
                ebay_data = data["ebay_scraped"]
                row.update({
                    "ebay_count": ebay_data.get("count", 0),
                    "ebay_avg": ebay_data.get("average_price", 0),
                    "ebay_median": ebay_data.get("median_price", 0),
                    "ebay_min": ebay_data.get("min_price", 0),
                    "ebay_max": ebay_data.get("max_price", 0),
                    "ebay_confidence": ebay_data.get("confidence_level", 0)
                })
                # Extract condition distribution if available
                conditions = ebay_data.get("condition_counts", {})
                for condition, count in conditions.items():
                    row[f"condition_{condition.lower().replace(' ', '_')}"] = count
            
            # Extract Reverb data if available
            if "reverb" in data:
                reverb_data = data["reverb"]
                row.update({
                    "reverb_count": reverb_data.get("count", 0),
                    "reverb_avg": reverb_data.get("average_price", 0),
                    "reverb_median": reverb_data.get("median_price", 0),
                    "reverb_min": reverb_data.get("min_price", 0),
                    "reverb_max": reverb_data.get("max_price", 0)
                })
            
            data_rows.append(row)
        
        # Convert to DataFrame
        df = pd.DataFrame(data_rows)
        
        # Add age of data in days
        if not df.empty and "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            now = datetime.now()
            df["data_age_days"] = (now - df["timestamp"]).dt.total_seconds() / (24 * 3600)
        
        return df
    
    def analyze_price_distribution(self, df):
        """Analyze the price distribution and identify statistical outliers"""
        if df.empty:
            print("No data available for analysis")
            return df
        
        # Add price distribution metrics
        price_cols = [col for col in df.columns if col.endswith("_avg") or col.endswith("_median")]
        
        for col in price_cols:
            source = col.split("_")[0]
            if f"{source}_median" in df.columns and f"{source}_count" in df.columns:
                # Only analyze sources with sufficient data
                valid_items = df[df[f"{source}_count"] >= 5]
                if not valid_items.empty:
                    # Calculate z-scores for median prices
                    median_col = f"{source}_median"
                    mean = valid_items[median_col].mean()
                    std = valid_items[median_col].std()
                    if std > 0:
                        df[f"{source}_zscore"] = (df[median_col] - mean) / std
        
        return df
    
    def identify_deals(self, df):
        """Identify items that are potentially good deals or overpriced"""
        if df.empty:
            return df
        
        # First focus on eBay data as it's most reliable for auction comparisons
        if "ebay_median" in df.columns:
            df["ebay_deal_score"] = np.nan
            mask = df["ebay_count"] >= 5  # Only consider items with sufficient data
            
            # Calculate deal score (lower is better deal)
            # A score of 1.0 means it's at the median market price
            # Below 1.0 is a potential deal, above 1.0 is potentially overpriced
            df.loc[mask, "ebay_deal_score"] = df.loc[mask, "avg_price"] / df.loc[mask, "ebay_median"]
            
            # Categorize items
            df["price_category"] = "fair_price"  # Default
            df.loc[df["ebay_deal_score"] <= self.deal_threshold, "price_category"] = "good_deal"
            df.loc[df["ebay_deal_score"] >= self.overpriced_threshold, "price_category"] = "overpriced"
        
        # Add optimal bid price - typically 10-15% below median for auctions
        if "ebay_median" in df.columns:
            # Base optimal price on median, but adjust based on condition distribution
            df["optimal_bid_price"] = df["ebay_median"] * 0.85  # Default: 15% below median
            
            # Adjust for items with more "new" or "like new" conditions
            if "condition_new" in df.columns and "condition_like_new" in df.columns:
                total_condition = df["ebay_count"].fillna(0)
                premium_condition = df["condition_new"].fillna(0) + df["condition_like_new"].fillna(0)
                
                # If more than 50% are in premium condition, adjust optimal price up
                premium_ratio = premium_condition / total_condition
                df["optimal_bid_price"] = df["optimal_bid_price"] * (1 + premium_ratio * 0.1)
        
        return df
    
    def plot_price_distribution(self, df, output_prefix="price_distribution"):
        """Generate plots for price distribution analysis"""
        if df.empty or "ebay_median" not in df.columns:
            print("Insufficient data for plotting price distributions")
            return
        
        # Filter to items with sufficient data
        plot_df = df[df["ebay_count"] >= 5].copy()
        if plot_df.empty:
            print("Insufficient data for plotting after filtering")
            return
        
        # 1. Price distribution by source
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=plot_df[["ebay_median", "avg_price"]].melt())
        plt.title("Price Distribution by Source")
        plt.ylabel("Price ($)")
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, f"{output_prefix}_boxplot.png"))
        
        # 2. Deal score distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(plot_df["ebay_deal_score"].dropna(), bins=20)
        plt.axvline(x=self.deal_threshold, color='g', linestyle='--', 
                   label=f'Deal Threshold ({self.deal_threshold})')
        plt.axvline(x=self.overpriced_threshold, color='r', linestyle='--', 
                   label=f'Overpriced Threshold ({self.overpriced_threshold})')
        plt.axvline(x=1.0, color='b', linestyle='-', label='Fair Price (1.0)')
        plt.title("Deal Score Distribution (Lower = Better Deal)")
        plt.xlabel("Deal Score (Price / Median Market Price)")
        plt.ylabel("Count")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, f"{output_prefix}_deal_score.png"))
        
        # 3. Scatterplot of price vs. confidence
        plt.figure(figsize=(10, 6))
        sns.scatterplot(x="ebay_count", y="ebay_deal_score", 
                       hue="price_category", data=plot_df)
        plt.title("Deal Score vs. Data Points Count")
        plt.xlabel("Number of Data Points")
        plt.ylabel("Deal Score (Lower = Better Deal)")
        plt.tight_layout()
        plt.savefig(os.path.join(self.plot_dir, f"{output_prefix}_confidence.png"))
        
        plt.close('all')
    
    def generate_deal_report(self, df, output_file="price_analysis.csv"):
        """Generate a report of deals and price analysis"""
        if df.empty:
            print("No data available for report generation")
            return
        
        # Select and rename relevant columns for the report
        report_cols = [
            "item_description", "price_category", "avg_price", "ebay_median", 
            "ebay_deal_score", "optimal_bid_price", "ebay_count", 
            "confidence", "data_age_days"
        ]
        
        # Filter to columns that exist
        report_cols = [col for col in report_cols if col in df.columns]
        if not report_cols:
            print("No relevant columns for report")
            return
        
        report_df = df[report_cols].copy()
        
        # Sort by deal score (ascending = best deals first)
        if "ebay_deal_score" in report_df.columns:
            report_df = report_df.sort_values("ebay_deal_score")
        
        # Save to CSV
        output_path = os.path.join(self.output_dir, output_file)
        report_df.to_csv(output_path, index=False)
        print(f"Price analysis report saved to {output_path}")
        
        return report_df
    
    def run_full_analysis(self):
        """Run a complete analysis pipeline"""
        print("Loading price data...")
        df = self.load_price_data()
        
        if df.empty:
            print("No price data available. Please run price gathering first.")
            return None
        
        print(f"Loaded data for {len(df)} items")
        
        print("Analyzing price distribution...")
        df = self.analyze_price_distribution(df)
        
        print("Identifying deals...")
        df = self.identify_deals(df)
        
        print("Generating plots...")
        self.plot_price_distribution(df)
        
        print("Generating deal report...")
        report_df = self.generate_deal_report(df)
        
        print("Analysis complete!")
        return report_df


def main():
    """Main function to run the price analyzer"""
    analyzer = PriceAnalyzer()
    results = analyzer.run_full_analysis()
    
    if results is not None and not results.empty:
        # Display summary of findings
        deal_counts = results["price_category"].value_counts()
        print("\n=== Price Analysis Summary ===")
        print(f"Total items analyzed: {len(results)}")
        for category, count in deal_counts.items():
            print(f"{category}: {count} items")
        
        # Show top 5 deals
        good_deals = results[results["price_category"] == "good_deal"]
        if not good_deals.empty:
            print("\n=== Top 5 Best Deals ===")
            top_deals = good_deals.head(5)
            for idx, row in top_deals.iterrows():
                save_pct = (1 - row["ebay_deal_score"]) * 100
                print(f"{row['item_description']}: ${row['avg_price']:.2f} vs. market ${row['ebay_median']:.2f} ({save_pct:.1f}% savings)")


if __name__ == "__main__":
    main()
