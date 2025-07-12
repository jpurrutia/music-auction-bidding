#!/usr/bin/env python3
"""
Auction CLI - Command-line interface for auction analysis
"""
import argparse
import os
import sys
import pandas as pd
from tabulate import tabulate
from duckdb_analyzer import DuckDBAnalyzer

# Import real auction analyzer functionality
try:
    from real_auction_analyzer import RealAuctionAnalyzer
except ImportError:
    print(
        "Warning: real_auction_analyzer.py not found. Real auction analysis will not be available."
    )


def print_table(df, max_rows=None):
    """Print dataframe as a pretty table"""
    if max_rows:
        df = df.head(max_rows)
    print(tabulate(df, headers="keys", tablefmt="pretty", showindex=False))


def main():
    parser = argparse.ArgumentParser(description="Music Auction Analysis CLI")

    # Main command arguments
    parser.add_argument(
        "--data-file", type=str, default="data.txt", help="Path to auction data file"
    )
    parser.add_argument(
        "--analyzer",
        type=str,
        choices=["duckdb", "real"],
        default="duckdb",
        help="Analysis engine to use (duckdb: simulated data, real: eBay market data)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=15,
        help="Maximum number of items to analyze (for real analyzer)",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Use random sampling instead of first N items (for real analyzer)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh of cached market data (for real analyzer)",
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Summary command
    summary_parser = subparsers.add_parser("summary", help="Show analysis summary")

    # Top deals command
    top_parser = subparsers.add_parser("top", help="Show top deals")
    top_parser.add_argument(
        "--count", type=int, default=10, help="Number of deals to show"
    )

    # Category command
    category_parser = subparsers.add_parser("category", help="Show deals by category")
    category_parser.add_argument(
        "category", type=str, help='Category to filter by (e.g., "Electric Guitar")'
    )

    # Rating command
    rating_parser = subparsers.add_parser("rating", help="Show deals by rating")
    rating_parser.add_argument(
        "rating",
        type=str,
        choices=["Great Deal", "Good Deal", "Fair Deal", "Overpriced"],
        help="Rating to filter by",
    )

    # Item command
    item_parser = subparsers.add_parser("item", help="Show details for a specific item")
    item_parser.add_argument("item_number", type=int, help="Item number to show")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export analysis results")
    export_parser.add_argument(
        "--output-dir", type=str, default="results", help="Directory to save results"
    )

    # Visualize command
    viz_parser = subparsers.add_parser("visualize", help="Generate visualizations")
    viz_parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory to save visualizations",
    )

    # Parse arguments
    args = parser.parse_args()

    # Create appropriate analyzer based on selection
    if args.analyzer == "real":
        if "RealAuctionAnalyzer" not in globals():
            print(
                "Error: Real auction analyzer not available. Please ensure real_auction_analyzer.py exists."
            )
            sys.exit(1)

        print(
            f"Using real-time eBay market data analyzer with {'random sampling' if args.random else 'first N items'}"
        )
        analyzer = RealAuctionAnalyzer(
            auction_file="data/auction_items.txt",
            max_items=args.max_items,
            random_sample=args.random,
            refresh_market_data=args.refresh,
        )
        # Run the analysis
        analyzer.load_auction_data()
        analyzer.fetch_market_prices()
        analyzer.analyze_deals()

        # For backward compatibility, make deal_analysis available
        analyzer.deal_analysis = analyzer.results_df
    else:
        # Default to DuckDB analyzer with simulated data
        print("Using DuckDB analyzer with simulated market data")
        analyzer = DuckDBAnalyzer(args.data_file)
        analyzer.parse_data()
        analyzer.fetch_market_prices()
        analyzer.calculate_deals()  # Make sure to calculate deals before accessing deal_analysis

    # Handle commands
    if args.command == "summary":
        if args.analyzer == "real":
            analyzer.print_summary()
        else:
            analyzer.print_summary()

    elif args.command == "top":
        if args.analyzer == "real":
            # For real analyzer, we sort by deal_score ascending (lower is better)
            top_deals = analyzer.results_df.sort_values("deal_score").head(args.count)
            print(f"\nTop {args.count} Deals:")
            print_table(top_deals)
        else:
            top_deals = analyzer.get_top_deals(args.count)
            print(f"\nTop {args.count} Deals:")
            print_table(top_deals)

    elif args.command == "category":
        if args.analyzer == "real":
            if "category" in analyzer.results_df.columns:
                category_deals = analyzer.results_df[
                    analyzer.results_df["category"].str.contains(
                        args.category, case=False
                    )
                ]
                if len(category_deals) == 0:
                    print(f"No items found in category: {args.category}")
                    print("Available categories:")
                    categories = analyzer.results_df["category"].unique()
                    for cat in categories:
                        print(f"- {cat}")
                else:
                    print(f"\nDeals in category '{args.category}':")
                    print_table(category_deals)
            else:
                print(
                    "Category information not available in real auction analyzer results"
                )
        else:
            category_deals = analyzer.get_deals_by_category(args.category)
            if len(category_deals) == 0:
                print(f"No items found in category: {args.category}")
                print("Available categories:")
                categories = analyzer.con.execute(
                    "SELECT DISTINCT category FROM items"
                ).fetchall()
                for cat in categories:
                    print(f"- {cat[0]}")
            else:
                print(f"\nDeals in category '{args.category}':")
                print_table(category_deals)

    elif args.command == "rating":
        rating_deals = analyzer.get_deals_by_rating(args.rating)
        print(f"\nItems rated as '{args.rating}':")
        print_table(rating_deals)

    elif args.command == "item":
        if args.analyzer == "real":
            # For real auction analyzer
            lot_number = args.item_number

            # No longer need debug output

            # Try different approaches to match the lot number
            # First, try direct comparison
            item_details = analyzer.results_df[analyzer.results_df["lot"] == lot_number]

            # If no match, try converting to int if lot is stored as string
            if len(item_details) == 0 and "lot" in analyzer.results_df.columns:
                # Try converting lot_number to string for comparison
                item_details = analyzer.results_df[
                    analyzer.results_df["lot"].astype(str) == str(lot_number)
                ]

            # If still no match, try with item_number
            if len(item_details) == 0 and "item_number" in analyzer.results_df.columns:
                item_details = analyzer.results_df[
                    analyzer.results_df["item_number"] == lot_number
                ]

            if len(item_details) == 0:
                print(f"No item found with lot number: {lot_number}")
                return

            item = item_details.iloc[0]
            print(f"\n=== AUCTION ITEM #{lot_number} ANALYSIS ===\n")
            print(f"Description: {item['description']}")
            if "category" in item:
                print(f"Category: {item['category']}")

            # Price Information
            print("\n📊 PRICE INFORMATION:")
            retail_price = (
                f"${item['retail_price']:.2f}"
                if not pd.isna(item["retail_price"])
                else "$0.00"
            )
            starting_bid = (
                f"${item['starting_bid']:.2f}"
                if not pd.isna(item["starting_bid"])
                else "$0.00"
            )
            market_price = (
                f"${item['market_price']:.2f}"
                if not pd.isna(item["market_price"])
                else "$0.00"
            )

            print(f"Retail Price:  {retail_price}")
            print(f"Starting Bid:  {starting_bid}")
            print(f"Market Value:  {market_price}")

            # Deal Analysis
            print("\n📈 DEAL ANALYSIS:")
            if "optimal_bid" in item:
                optimal_bid = (
                    f"${item['optimal_bid']:.2f}"
                    if not pd.isna(item["optimal_bid"])
                    else "$0.00"
                )
                print(f"OPTIMAL BID:   {optimal_bid} 👈 Your maximum bid")

            # Deal Score and Savings
            if "deal_score" in item:
                deal_score = (
                    item["deal_score"] if not pd.isna(item["deal_score"]) else 0.0
                )
                print(f"Deal Score:    {deal_score:.3f} (Lower is better)")

            if "savings_pct" in item:
                savings = (
                    item["savings_pct"] if not pd.isna(item["savings_pct"]) else 0.0
                )
                if savings > 0:
                    print(f"Savings:       {savings:.1f}% below market value ✅")
                else:
                    print(f"Premium:       {abs(savings):.1f}% above market value ⚠️")

            # Deal Category and Confidence
            if "deal_category" in item and "confidence" in item:
                deal_category = (
                    item["deal_category"]
                    if not pd.isna(item["deal_category"])
                    else "Unknown"
                )
                confidence = (
                    item["confidence"] if not pd.isna(item["confidence"]) else 0.0
                )

                rating_symbol = (
                    "⭐⭐⭐"
                    if deal_category == "good_deal"
                    else "⭐" if deal_category == "fair_price" else "❌"
                )
                print(
                    f"Deal Rating:   {deal_category.replace('_', ' ').title()} {rating_symbol}"
                )
                print(f"Confidence:    {confidence:.0f}%")

            # Bidding advice
            print("\n💰 BIDDING ADVICE:")
            if "deal_category" in item:
                if item["deal_category"] == "good_deal":
                    print(
                        "This is a GOOD DEAL! Bid up to the optimal bid price for good value."
                    )
                elif item["deal_category"] == "fair_price":
                    print(
                        "This is a FAIR PRICE. Consider bidding if you really want this item."
                    )
                else:
                    print(
                        "This item appears OVERPRICED. Consider skipping unless you specifically need it."
                    )

        else:
            # For DuckDB analyzer
            item_details = analyzer.con.execute(
                f"""
                SELECT * FROM deal_analysis WHERE item_number = {args.item_number}
            """
            ).fetchdf()

            if len(item_details) == 0:
                print(f"No item found with item number: {args.item_number}")
            else:
                print(f"\nDetails for Item #{args.item_number}:")
                item = item_details.iloc[0]
                print(f"Description: {item['description']}")
                print(f"Category: {item['category']}")

                # Price Information
                print("\nPrice Information:")
                retail_price = (
                    f"${item['retail_price']:.2f}"
                    if not pd.isna(item["retail_price"])
                    else "$0.00"
                )
                starting_bid = (
                    f"${item['starting_bid']:.2f}"
                    if not pd.isna(item["starting_bid"])
                    else "$0.00"
                )
                print(f"Retail Price: {retail_price}")
                print(f"Starting Bid: {starting_bid}")

                # Market Data from Reverb
                print("\nMarket Data (Reverb):")
                market_price = (
                    f"${item['market_price']:.2f}"
                    if not pd.isna(item["market_price"])
                    else "$0.00"
                )
                median_price = (
                    f"${item['median_price']:.2f}"
                    if not pd.isna(item["median_price"])
                    else "$0.00"
                )
                min_price = (
                    f"${item['min_price']:.2f}"
                    if not pd.isna(item["min_price"])
                    else "$0.00"
                )
                max_price = (
                    f"${item['max_price']:.2f}"
                    if not pd.isna(item["max_price"])
                    else "$0.00"
                )
                print(f"Average Market Price: {market_price}")
                print(f"Median Price: {median_price}")
                print(f"Price Range: {min_price} - {max_price}")
                print(f"Number of Listings: {item['listing_count']}")
                print(
                    f"Most Common Condition: {item['top_condition'] if not pd.isna(item['top_condition']) else 'Unknown'}"
                )
                print(f"Data Source: {item['source_type']}")

                # Analysis
                print("\nDeal Analysis:")
                optimal_price = (
                    f"${item['optimal_price']:.2f}"
                    if not pd.isna(item["optimal_price"])
                    else "$0.00"
                )
                deal_score = (
                    f"{item['deal_score']:.1f}%"
                    if not pd.isna(item["deal_score"])
                    else "0.0%"
                )
                data_confidence = (
                    f"{item['data_confidence']}%"
                    if not pd.isna(item["data_confidence"])
                    else "0%"
                )

                print(f"Optimal Price: {optimal_price}")
                print(f"Deal Score: {deal_score}")
                print(f"Deal Rating: {item['deal_rating']}")
                print(f"Data Confidence: {data_confidence}")
                print(f"Market Volatility: {item['market_volatility']}")

            # Market vs Retail
            if not pd.isna(item["retail_market_gap"]):
                gap_value = abs(item["retail_market_gap"])
                gap_str = f"{gap_value:.1f}%"

                if item["retail_market_gap"] > 0:
                    print(f"\nRetail price is {gap_str} above market value")
                elif item["retail_market_gap"] < 0:
                    print(f"\nRetail price is {gap_str} below market value")
                else:
                    print("\nRetail price matches market value")
            else:
                print("\nInsufficient data to compare retail and market prices")

            # Show similar items with enhanced market data
            print("\nSimilar items in same category:")
            similar = analyzer.con.execute(
                f"""
                SELECT 
                    item_number, 
                    description, 
                    starting_bid,
                    market_price,
                    median_price,
                    listing_count,
                    deal_score,
                    deal_rating,
                    data_confidence
                FROM deal_analysis 
                WHERE 
                    category = '{item['category']}' AND 
                    item_number != {args.item_number}
                ORDER BY deal_score DESC
                LIMIT 5
            """
            ).fetchdf()
            print_table(similar)

    elif args.command == "export":
        if args.analyzer == "real":
            os.makedirs(args.output_dir, exist_ok=True)
            export_path = os.path.join(args.output_dir, "real_auction_analysis.csv")
            analyzer.results_df.to_csv(export_path, index=False)
            print(f"Results exported to {export_path}")
        else:
            analyzer.export_results(args.output_dir)
            print(f"Results exported to {args.output_dir}/")

    elif args.command == "visualize":
        if args.analyzer == "real":
            analyzer.create_visualizations(output_dir=args.output_dir)
            print(f"Visualizations saved to {args.output_dir}/")
        else:
            analyzer.create_visualizations(args.output_dir)
            print(f"Visualizations saved to {args.output_dir}/")

    else:
        # If no command specified, show help
        parser.print_help()


if __name__ == "__main__":
    main()
