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
4. **Categorization**: Items are classified into deal quality tiers based on score and data confidence
5. **Visualization**: Results are presented in both tabular and graphical formats

## Market Price Research Methodology

### Reverb API Integration

This system integrates with the [Reverb API](https://www.reverb.com/page/api) to fetch real-time market data for musical instruments. The process works as follows:

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

### Optimal Price Calculation

The system calculates an optimal price by weighing market data and retail prices, with the weighting dynamically adjusted based on data confidence:

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

1. Ensure you have Python installed with the required dependencies:
   ```
   uv venv  # Creates virtual environment
   source .venv/bin/activate  # Activate the environment
   uv pip install -r requirements.txt
   ```

2. Run the analysis with the command-line interface:
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
- **Value Percentage**: Starting bid as a percentage of optimal price
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

| Task ID | Feature | Description | Status | Priority | Est. Time | Notes |
|---------|---------|-------------|--------|----------|-----------|-------|
| 1 | Reverb API Integration | Core API integration for market price fetching | Complete | High | - | MVP feature |
| 2 | `test_reverb_api.py` Script | Test script for API configuration validation | Complete | High | - | Implemented with command-line options |
| 3 | Additional API Sources | Integration with eBay and Sweetwater APIs | Not Started | High | 5-7 days | Enhances data quality and confidence |
| 4 | Enhanced Search Algorithm | NLP-based text matching for better results | Not Started | High | 3-4 days | Improves market data relevance |
| 9 | Market Data Enrichment | Additional market metrics and price modeling | Not Started | High | 4-6 days | Improves price calculation quality |
| 6 | Error Logging | Comprehensive error handling for API failures | Not Started | Medium | 1-2 days | Reliability feature |
| 7 | Unit Tests | Test suite for calculation accuracy | Not Started | Medium | 3-4 days | Quality assurance |
| 5 | Deal Visualizations | Charts and graphs for deal analysis | In Progress | Medium | 2-3 days | Started with basic plots |
| 8 | Brand/Model Recognition | Advanced parsing for better market matching | Not Started | Medium | 4-5 days | Advanced feature |

### Priority Focus: Data Quality & Pricing Improvements

Based on current priorities, we're focusing on improving data quality and pricing calculation accuracy. The following tasks have been prioritized:

1. **Task 3: Additional API Sources** - Adding eBay API integration first to complement Reverb data with a broader marketplace
2. **Task 4: Enhanced Search Algorithm** - Improving text matching to get more relevant market listings
3. **Task 9: Market Data Enrichment** - Implementing condition modeling, brand value retention analysis, and price trend detection

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

#### Task 3: Additional API Sources (5-7 days)
- [ ] Research eBay API requirements and endpoints (0.5 day)
- [ ] Implement eBay API authentication (0.5 day)
- [ ] Create eBay search function in market_scraper.py (1 day)
- [ ] Research Sweetwater scraping approach (0.5 day)
- [ ] Implement Sweetwater product search (1 day)
- [ ] Add Guitar Center API integration (1 day)
- [ ] Implement Thomann music store data source (1 day)
- [ ] Research and add Musician's Friend price data (0.5 day)
- [ ] Create data normalization for cross-platform comparison (1 day)
- [ ] Implement weighted aggregation of prices from multiple sources (0.5 day)
- [ ] Update confidence calculation to consider multiple sources (0.5 day)
- [ ] Enhance caching for multiple data sources (0.5 day)
- [ ] Add source reliability scoring (0.5 day)

#### Task 4: Enhanced Search Algorithm (3-4 days)
- [ ] Implement basic text normalization (lowercase, remove special chars) (0.5 day)
- [ ] Add brand and model extraction from item descriptions (0.5 day)
- [ ] Create keyword importance weighting system (0.5 day)
- [ ] Implement fuzzy matching for similar instrument names (0.5 day)
- [ ] Add condition-aware matching (0.5 day)
- [ ] Implement price range filtering (0.5 day)
- [ ] Create confidence scoring for search match quality (0.5 day)
- [ ] Add fallback search strategies for zero-result queries (0.5 day)

#### Task 8: Brand/Model Recognition (4-5 days)
- [ ] Create dictionary of known instrument brands (0.5 day)
- [ ] Implement regex patterns for common model number formats (0.5 day)
- [ ] Create training dataset of instrument descriptions with labeled brands/models (1 day)
- [ ] Implement rule-based brand and model extraction (1 day)
- [ ] Add context-aware model number identification (1 day)
- [ ] Create fuzzy brand name matching (0.5 day)

#### Task 9: Market Data Enrichment (4-6 days)
- [ ] Implement condition impact modeling (1 day)
- [ ] Create brand value retention analysis (1 day)
- [ ] Add price trend detection and analysis (1 day)
- [ ] Implement statistical outlier detection (0.5 day)
- [ ] Add market volatility calculations (0.5 day)
- [ ] Create data confidence scoring system (0.5 day)
- [ ] Implement item rarity assessment (0.5 day)
- [ ] Add seasonality detection for pricing (0.5 day)
- [ ] Create cross-reference validation between data sources (0.5 day)
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
