# Music Auction Bidding Analysis

This project analyzes music instrument auction data to identify optimal prices and find the best deals. It combines data analytics with market price research to help make informed bidding decisions.

## Features

- **Parse Auction Data**: Extracts item details, retail prices, and starting bids from auction listings
- **Market Price Research**: Simulates (and can be extended for actual) web scraping from sites like Reverb, eBay, and Sweetwater
- **Deal Analysis**: Calculates optimal prices and deal scores based on market data
- **Data Visualization**: Creates charts showing deal distribution and price comparisons
- **Category Analysis**: Groups items by instrument type for targeted analysis

## Components

### 1. Data Files
- `data.txt` - Raw auction data with item descriptions, retail prices, and starting bids

### 2. Analysis Scripts
- `auction_analyzer.py` - Basic pandas-based analyzer for quick analysis
- `market_scraper.py` - Web scraping module for gathering market prices
- `duckdb_analyzer.py` - Enhanced analyzer using DuckDB for efficient data processing and visualization

## How It Works

1. **Data Parsing**: The system reads auction listings and extracts structured data
2. **Market Research**: For each item, the system queries multiple sources to determine fair market value
3. **Deal Scoring**: Each item receives a deal score based on the difference between starting bid and optimal price
4. **Categorization**: Items are classified as "Great Deal", "Good Deal", "Fair Deal", or "Overpriced"
5. **Visualization**: Results are presented in both tabular and graphical formats

## Deal Scoring Logic

The system calculates an optimal price using the following formula:
```
optimal_price = (0.6 * market_price) + (0.4 * retail_price)
```

Deal scores are calculated as a percentage:
```
deal_score = ((optimal_price - starting_bid) / optimal_price) * 100
```

Items are then categorized:
- **Great Deal**: Score ≥ 50%
- **Good Deal**: 30% ≤ Score < 50%
- **Fair Deal**: 0% ≤ Score < 30%
- **Overpriced**: Score < 0%

## Usage

1. Ensure you have Python installed with the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the basic analyzer:
   ```
   python auction_analyzer.py
   ```

3. Run the enhanced DuckDB analyzer (includes visualizations):
   ```
   python duckdb_analyzer.py
   ```

4. Results will be exported to CSV files and visualizations will be saved as PNG files in the "results" directory.

## Extending This Project

### Adding Real Web Scraping
The current implementation uses simulated market prices. To implement actual web scraping:

1. Modify the `market_scraper.py` file
2. Implement the `search_reverb()`, `search_ebay()`, and `search_sweetwater()` methods
3. Be mindful of rate limiting and robots.txt rules

### Adding New Data Sources
To add new auction data:

1. Create a new text file following the same format as `data.txt`
2. Update the file path when running the analyzers

## Output Examples

The analysis generates:
- Comprehensive CSV files with all analyzed data
- Category-specific analyses
- Visualization charts showing deal distributions and price comparisons
- Summary statistics in the terminal output

## Future Improvements

- Implement machine learning for price prediction
- Add historical price tracking to identify trends
- Create a web interface for interactive analysis
- Add email notifications for newly listed "Great Deals"
