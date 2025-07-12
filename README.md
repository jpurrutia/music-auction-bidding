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
- `auction_analyzer.py` - Basic pandas-based analyzer for quick analysis with simulated data
- `real_auction_analyzer.py` - Enhanced analyzer using real eBay market data to find optimal prices and deal scores
- `market_scraper.py` - Web scraping module for gathering real-time market prices from eBay and other sources
- `duckdb_analyzer.py` - Enhanced analyzer using DuckDB for efficient data processing and visualization

## How It Works

1. **Data Parsing**: The system reads auction listings and extracts structured data from text files
2. **Market Research**: For each item, the system queries multiple sources (primarily eBay) to determine fair market value
3. **Deal Scoring**: Each item receives a deal score based on the starting bid compared to market median price
4. **Optimal Bid Calculation**: Optimal bid prices are calculated based on market data, retail prices, and confidence levels
5. **Categorization**: Items are classified as "good deal", "fair price", or "overpriced" based on deal score thresholds
6. **Visualization**: Results are presented in visualizations and CSV reports with detailed market insights

## Market Price Research Methodology

### eBay Market Data Integration

This system primarily uses eBay sold listings data for real-time market analysis. The eBay scraping process works as follows:

1. **Search Query Formation**:
   - Item descriptions are cleaned and formatted for optimal eBay search results
   - Non-essential words are filtered out to focus on key product identifiers
   - Search is configured to only show "sold listings" to get actual market prices

2. **Web Scraping & Pagination**:
   - Requests simulate a browser with rotating user-agents to avoid detection
   - Multiple pages are scraped (up to 5 by default) to gather sufficient data points
   - Rate limiting is implemented to respect eBay's server constraints
   - Results are cached locally to minimize redundant scraping

3. **Data Extraction**:
   - BeautifulSoup is used to parse HTML and extract listing prices, conditions, and dates
   - Listing conditions are standardized into categories (Excellent, Good, Fair, Poor)
   - Outliers beyond 2 standard deviations are filtered to improve data quality
   - Statistical metrics are calculated (mean, median, min/max prices)

### Reverb API Integration (Secondary)

As a secondary source, the system can integrate with the [Reverb API](https://www.reverb.com/page/api) to fetch additional market data for musical instruments. The process works as follows:

1. **Search Query Formation**:
   - The item description is cleaned and formatted for API compatibility
   - Special characters are removed and spaces are encoded
   - Search prioritizes exact matches on brand names and model numbers

2. **API Request & Authentication**:
   - Requests are sent to Reverb's REST API endpoint using a personal OAuth Bearer token
   - Requests include appropriate headers and pagination parameters
   - Rate limiting is respected to avoid API usage restrictions

3. **Response Processing**:
   - JSON responses are parsed to extract listing details, prices, and conditions
   - Statistical calculations are performed (average, median, minimum, maximum)
   - Condition breakdowns are compiled to assess value distribution
   - Sample listings are stored for reference

4. **Caching System**:
   - API responses are cached locally to minimize redundant API calls
   - Default cache expiry is 7 days (configurable)
   - Timestamps validate cache freshness
   - Cache uses item descriptions as keys for quick retrieval

5. **Fallback Mechanism**:
   - If the API returns no results or encounters an error, the system falls back to simulated data
   - Simulation uses a random normal distribution based on the retail price
   - Simulated data is clearly marked as such in the output

### Search Matching Confidence

The system provides a confidence metric for market data reliability:

| Listing Count | Confidence Level | Rationale |
|--------------|-----------------|------------|
| 20+ listings | 100% | Statistically significant sample size |
| 10-19 listings | 80% | Good sample with minor statistical limitations |
| 5-9 listings | 60% | Moderate sample with potential for outlier influence |
| 1-4 listings | 40% | Limited data points, reduced statistical reliability |
| 0 listings (simulation) | 20% | Entirely estimated data |

## Deal Scoring Logic

### Deal Score Calculation

The deal score is calculated as the ratio of starting bid to market median price:

```python
deal_score = starting_bid / market_median_price
```

A deal score below 1.0 indicates a potential good deal, with lower scores being better deals.

### Item Classification

Items are classified into three categories based on their deal scores:

1. **Good Deal**: Score ≤ 0.85 (starting bid is at least 15% below market median)
2. **Fair Price**: 0.85 < Score < 1.15 (starting bid is within 15% of market median)
3. **Overpriced**: Score ≥ 1.15 (starting bid is at least 15% above market median)

These thresholds are configurable via environment variables (DEAL_THRESHOLD and OVERPRICED_THRESHOLD).

### Optimal Price Calculation

The system calculates an optimal bid price by weighing market data and retail prices, with the weighting dynamically adjusted based on data confidence:

```python
# With high data confidence (many listings)
optimal_price = (0.7 * market_price) + (0.3 * retail_price)

# With moderate data confidence
optimal_price = (0.6 * market_price) + (0.4 * retail_price)

# With low data confidence (few or no listings)
optimal_price = (0.4 * market_price) + (0.6 * retail_price)
```

### Market Price Determination

Market price is calculated based on data from Reverb API listings:

1. For instruments with sufficient listings, we prioritize the **median price** rather than the average to reduce the impact of outliers
2. When the market has high volatility (large price spread), we increase the weighting of retail price
3. Condition breakdown affects price expectations (e.g., "Excellent" condition commands higher prices)

### Deal Score Calculation

Deal scores are calculated as a percentage discount from the optimal price:

```python
deal_score = ((optimal_price - starting_bid) / optimal_price) * 100
```

### Enhanced Deal Rating System

Items are categorized with a sophisticated rating system that considers both deal score and data confidence:

- **Exceptional Deal**: Score ≥ 60% with high data confidence (5+ listings)
- **Great Deal**: Score ≥ 50%
- **Good Deal**: 30% ≤ Score < 50%
- **Fair Deal**: 15% ≤ Score < 30%
- **Slight Deal**: 0% ≤ Score < 15%
- **Overpriced**: Score < 0%

### Market Volatility Assessment

The system calculates price volatility as a percentage of the spread between minimum and maximum prices:

```python
volatility = ((max_price - min_price) / median_price) * 100
```

Volatility is categorized as:
- **Low**: ≤ 20%
- **Medium**: 20-50%
- **High**: > 50%

This volatility assessment helps users understand the stability of the market for that particular instrument type.

## Reverb API Integration Setup

### Setting Up API Access

1. **Get a Reverb API Key**:
   - Create a developer account at [Reverb Developer Portal](https://reverb.com/page/api)
   - Generate a personal API token with read permissions
   - Copy your API token for the next step

2. **Configure Environment Variables**:
   - Create a `.env` file in the project root based on the provided `.env.template`
   - Add your Reverb API token to the configuration
   ```
   REVERB_API_TOKEN=your_token_here
   USE_SANDBOX=false
   CACHE_EXPIRY_DAYS=7
   ```

3. **Test the API Integration**:
   - Run the included test script to validate your API setup
   ```
   python test_reverb_api.py
   ```
   - Successful results will show sample listings and price statistics

### Caching System

The market price data is cached to minimize API calls:

- **Cache Location**: Data is stored in the `cache/` directory as JSON files
- **Cache Key**: Each search query generates a unique cache key based on the item description
- **Expiration**: Cache entries expire after the configured number of days (default: 7 days)
- **Manual Refresh**: Force cache refresh by setting `refresh_cache=True` or deleting cache files

## Usage

### Running the Real Auction Analyzer

To analyze actual auction items with real eBay market data:

```bash
uv run python real_auction_analyzer.py --max-items 15 --random --refresh
```

Options:
- `--max-items N`: Analyze at most N items (default: 15)
- `--random`: Use random sampling instead of first N items
- `--refresh`: Force refresh of cached market data

Output:
- Analysis results are saved to a timestamped folder in `cache/analysis/run_TIMESTAMP/`
- Visualizations are generated showing deal scores, price comparisons, and savings percentages
- A CSV report is created with detailed information for each item

### Running the Basic Auction Analyzer with the command-line interface:
   ```
   python auction_cli.py --data-file data.txt summary
   ```

3. View top deals:
   ```
   python auction_cli.py top 10
   ```

4. Filter by category:
   ```
   python auction_cli.py category "Guitar"
   ```

5. View details for a specific item:
   ```
   python auction_cli.py item 42
   ```

## Interpreting the Results

### Market Data Fields

For each item, the system provides:

- **Market Price**: Average price from current listings
- **Median Price**: Middle value of all listing prices (more resistant to outliers)
- **Price Range**: Minimum to maximum prices found in listings
- **Listing Count**: Number of comparable items found
- **Data Confidence**: Percentage indicating reliability of market data
- **Market Volatility**: Assessment of price stability in the marketplace
- **Source Type**: Whether data came from API or simulation

### Deal Quality Indicators

- **Deal Score**: Percentage discount from optimal price
- **Deal Rating**: Categorical assessment from "Exceptional Deal" to "Overpriced"
- **Savings Percentage**: (Market Price - Starting Bid) / Market Price * 100
- **Listing Count**: Number of market listings found for confidence assessment
- **Source**: Data source (ebay_scraped, ebay_api, reverb, sweetwater, or simulation)
- **Retail-Market Gap**: How retail price compares to current market value

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

### Search and Matching Enhancements
- **Multi-source Integration**: Implement parallel searches across eBay, Sweetwater, and other retailers
- **Intelligent Query Generation**: Use NLP to extract key instrument features for better search matching
- **Brand/Model Recognition**: Advanced parsing to identify brands and models from descriptions
- **Condition Weighting**: Apply market adjustments based on condition categorization
- **Image Recognition**: Add capability to identify instruments from images (long-term)

### Calculation Refinements
- **Implement machine learning for price prediction**: Train models on historical data to predict future prices
- **Adaptive confidence algorithms**: Dynamically adjust confidence scores based on market history
- **Brand-specific value retention**: Apply different depreciation models by manufacturer
- **Condition impact analysis**: Quantify exact value differences between conditions
- **Price trend analysis**: Factor in whether market prices are rising or falling

### System Improvements
- **Add historical price tracking**: Track market trends over time for each instrument category
- **Create a web interface**: Build interactive dashboard for analysis and visualization
- **Add email notifications**: Alert users when new "Exceptional Deals" are found
- **Cross-reference verification**: Validate prices across multiple platforms before calculating deal scores

## Development Status

### Implementation Tracking

This table serves as a control document for tracking implementation progress with estimated completion times:

| Task ID | Feature | Description | Status | Priority | Est. Time (Manual) | Est. Time (With AI) | Notes |
|---------|---------|-------------|--------|----------|-------------------|-------------------|-------|
| 1 | Reverb API Integration | Core API integration for market price fetching | Complete | High | - | - | MVP feature |
| 2 | `test_reverb_api.py` Script | Test script for API configuration validation | Complete | High | - | - | Implemented with command-line options |
| 3 | Additional API Sources | Integration with eBay and Sweetwater APIs | Not Started | High | 5-7 days | 2-3 days | Enhances data quality and confidence |
| 4 | Enhanced Search Algorithm | NLP-based text matching for better results | Not Started | High | 3-4 days | 1-2 days | Improves market data relevance |
| 9 | Market Data Enrichment | Additional market metrics and price modeling | Not Started | High | 4-6 days | 2-3 days | Improves price calculation quality |
| 6 | Error Logging | Comprehensive error handling for API failures | Not Started | Medium | 1-2 days | 0.5-1 day | Reliability feature |
| 7 | Unit Tests | Test suite for calculation accuracy | Not Started | Medium | 3-4 days | 1-2 days | Quality assurance |
| 5 | Deal Visualizations | Charts and graphs for deal analysis | In Progress | Medium | 2-3 days | 1 day | Started with basic plots |
| 8 | Brand/Model Recognition | Advanced parsing for better market matching | Not Started | Medium | 4-5 days | 1.5-2 days | Advanced feature |

### Priority Focus: Data Quality & Pricing Improvements

Based on current priorities, we're focusing on improving data quality and pricing calculation accuracy. With AI assistance, we can complete these priority tasks in approximately **5-8 days total** (compared to 12-17 days with manual development):

1. **Task 3: Additional API Sources** (1.5-2 days with AI)
   - Adding eBay API integration to complement Reverb with a broader general marketplace
   - Incorporating Sweetwater as primary retail source for true MSRP benchmark pricing
   - Leveraging Reverb Handpicked Collections for curated quality reference listings
   - Creating a cross-reference system between these sources to improve price confidence

2. **Task 4: Enhanced Search Algorithm** (1-2 days with AI)
   - Improving text matching to get more relevant market listings
   - Adding brand/model extraction for better matching accuracy
   - Implementing fuzzy matching for instrument variants

3. **Task 9: Market Data Enrichment** (2-3 days with AI)
   - Implementing condition modeling to adjust prices based on item condition
   - Creating brand value retention analysis to better evaluate depreciation
   - Adding price trend detection and statistical outlier handling
   
These improvements directly support the core objectives of finding optimal prices, identifying underpriced items, and calculating accurate deal scores based on comprehensive market data.

### Detailed Task Breakdown

Detailed subtasks for immediate implementation:

#### Task 2: Create `test_reverb_api.py` Script
- [x] Create basic script structure with command-line arguments
- [x] Implement environment variable loading (.env file support)
- [x] Add API connection test function
- [x] Create sample search query function
- [x] Implement result display formatting
- [x] Add error handling for common API issues
- [x] Write usage documentation in script comments

#### Task 5: Deal Visualizations
- [ ] Create price comparison bar charts (retail vs. market vs. optimal)
- [ ] Implement deal score distribution histogram
- [ ] Add scatter plot of deal score vs. data confidence
- [ ] Create category-based deal distribution chart
- [ ] Add market volatility visualization
- [ ] Implement interactive visualization options
- [ ] Add automatic chart saving to results directory

#### Task 6: Error Logging
- [ ] Implement structured logging system
- [ ] Add API request/response logging
- [ ] Implement rate limiting detection and handling
- [ ] Create error categorization system
- [ ] Add fallback mechanisms for all API operations
- [ ] Implement configurable log levels
- [ ] Add log rotation and management

#### Task 7: Unit Tests
- [ ] Create basic test framework setup
- [ ] Implement market price calculation tests
- [ ] Add deal scoring logic tests
- [ ] Create API response parsing tests
- [ ] Implement confidence calculation tests
- [ ] Add mock API response fixtures
- [ ] Create end-to-end test scenarios

#### Task 3: Additional API Sources (Manual: 3-4 days | With AI: 1.5-2 days)

##### Selected High-Value Sources
- **eBay API**: Large secondary marketplace with diverse pricing (complementary to Reverb)
- **Sweetwater**: Primary retail source for new instrument pricing (MSRP benchmark)
- **Reverb Handpicked Collections**: Curated listings from Reverb for quality reference points

##### Implementation Steps
- [ ] Research eBay API requirements and endpoints (Manual: 0.5 day | AI: 2 hours)
- [ ] Implement eBay API authentication (Manual: 0.5 day | AI: 3 hours)
- [ ] Create eBay search function in market_scraper.py (Manual: 1 day | AI: 4 hours)
- [ ] Research Sweetwater scraping approach (Manual: 0.5 day | AI: 2 hours)
- [ ] Implement Sweetwater product search (Manual: 1 day | AI: 3 hours)
- [ ] Extend Reverb API to access curated collections (Manual: 0.5 day | AI: 2 hours)
- [ ] Create data normalization for cross-platform comparison (Manual: 0.5 day | AI: 3 hours)
- [ ] Implement weighted aggregation of prices from multiple sources (Manual: 0.5 day | AI: 2 hours)
- [ ] Update confidence calculation to consider multiple sources (Manual: 0.5 day | AI: 2 hours)
- [ ] Enhance caching for multiple data sources (Manual: 0.5 day | AI: 2 hours)

#### Task 4: Enhanced Search Algorithm (Manual: 3-4 days | With AI: 1-2 days)
- [ ] Implement basic text normalization (lowercase, remove special chars) (Manual: 0.5 day | AI: 1 hour)
- [ ] Add brand and model extraction from item descriptions (Manual: 0.5 day | AI: 2 hours)
- [ ] Create keyword importance weighting system (Manual: 0.5 day | AI: 2 hours)
- [ ] Implement fuzzy matching for similar instrument names (Manual: 0.5 day | AI: 3 hours)
- [ ] Add condition-aware matching (Manual: 0.5 day | AI: 2 hours)
- [ ] Implement price range filtering (Manual: 0.5 day | AI: 1 hour)
- [ ] Create confidence scoring for search match quality (Manual: 0.5 day | AI: 3 hours)

## Live Auction Guide

### Quick Guide: Using the Auction Analysis Tool at a Live Auction

Here's how to use your music auction bidding analyzer during a live auction to find great deals and make smart bidding decisions:

### Before the Auction

1. **Prepare your auction data file**:
   - Create or update `data/auction_items.txt` with the auction catalog
   - Format each item as: `[Lot #] [Item Description] Retail $[amount] Starting Bid $[amount]`

2. **Pre-cache market data** (optional but recommended):
   ```bash
   uv run python auction_cli.py --analyzer real --max-items 100 summary
   ```
   This will fetch and cache eBay prices for all items, so you don't have to wait during the auction.

### During the Auction

#### Quick Deal Analysis

For a fast overview of all auction items:

```bash
uv run python auction_cli.py --analyzer real summary
```

This will show:
- Count and percentage of good deals, fair prices, and overpriced items
- List of the best deals with savings percentages
- List of most overpriced items to avoid

#### Find Top Deals

To see the best deals in the auction:

```bash
uv run python auction_cli.py --analyzer real top --count 10
```

This displays the top 10 deals ranked by deal score (lowest = best), showing market value, optimal bid price, and savings percentage for each.

#### Filter by Instrument Type

To focus on a specific category (like electric guitars):

```bash
uv run python auction_cli.py --analyzer real category "Electric Guitar"
```

Available categories include: "Electric Guitar", "Acoustic Guitar", "Bass Guitar", "Effects Pedal", "Percussion", etc.

#### Quick Lot Number Lookup (During Live Auction)

As the auctioneer calls out lot numbers, you can instantly analyze any specific item:

```bash
uv run python auction_cli.py --analyzer real item 7
```

This will give you a detailed analysis of lot #7, including:
- Item description and category
- Retail price, starting bid, and actual market value
- **Optimal bid price** - the maximum you should bid
- Deal score and savings percentage
- A clear recommendation on whether to bid or skip

### Live Auction Strategy

1. **Identify priority items** before bidding starts using the `top` and `category` commands
2. **Take notes** on your maximum bids based on the "optimal bid" values
3. **Stay disciplined** and don't exceed your maximum bids, especially for overpriced items

### Optimal Bidding

The tool shows three key values for each item:
- **Starting Bid**: The auction's opening bid price
- **Market Value**: The true market value based on eBay sold listings
- **Optimal Bid**: The recommended maximum bid (calculated based on market data and confidence)

Follow the optimal bid recommendations to avoid overbidding while still having a good chance of winning items that represent real value.

### Command Options

- `--max-items 50`: Analyze up to 50 items (default is 15)
- `--random`: Sample items randomly instead of using the first N items
- `--refresh`: Force refresh cached market data (use if prices might have changed)
- [ ] Add fallback search strategies for zero-result queries (Manual: 0.5 day | AI: 2 hours)

#### Task 8: Brand/Model Recognition (Manual: 4-5 days | With AI: 1.5-2 days)
- [ ] Create dictionary of known instrument brands (Manual: 0.5 day | AI: 2 hours)
- [ ] Implement regex patterns for common model number formats (Manual: 0.5 day | AI: 2 hours)
- [ ] Create training dataset of instrument descriptions with labeled brands/models (Manual: 1 day | AI: 4 hours)
- [ ] Implement rule-based brand and model extraction (Manual: 1 day | AI: 3 hours)
- [ ] Add context-aware model number identification (Manual: 1 day | AI: 4 hours)
- [ ] Create fuzzy brand name matching (Manual: 0.5 day | AI: 2 hours)

#### Task 9: Market Data Enrichment (Manual: 4-6 days | With AI: 2-3 days)
- [ ] Implement condition impact modeling (Manual: 1 day | AI: 4 hours)
- [ ] Create brand value retention analysis (Manual: 1 day | AI: 5 hours)
- [ ] Add price trend detection and analysis (Manual: 1 day | AI: 4 hours)
- [ ] Implement statistical outlier detection (Manual: 0.5 day | AI: 2 hours)
- [ ] Add market volatility calculations (Manual: 0.5 day | AI: 2 hours)
- [ ] Create data confidence scoring system (Manual: 0.5 day | AI: 3 hours)
- [ ] Implement item rarity assessment (Manual: 0.5 day | AI: 3 hours)
- [ ] Add seasonality detection for pricing (Manual: 0.5 day | AI: 2 hours)
- [ ] Create cross-reference validation between data sources (Manual: 0.5 day | AI: 3 hours)
- [ ] Add year/vintage extraction from descriptions
- [ ] Implement special edition/limited edition recognition

#### Task 9: Market Data Enrichment
- [ ] Add historical price tracking database
- [ ] Implement price trend analysis (rising/falling markets)
- [ ] Add condition impact modeling (price adjustments by condition)
- [ ] Create item rarity assessment system
- [ ] Implement seasonal market fluctuation tracking
- [ ] Add brand value retention modeling
- [ ] Implement geographical price difference analysis
- [ ] Create product lifecycle stage identification
- [ ] Add popular/trending item identification
- [ ] Implement cross-category price comparison
