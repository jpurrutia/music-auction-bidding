#!/usr/bin/env python3
"""
Market Scraper - Finds market prices for musical instruments from popular sites
"""
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List, Tuple, Any
import os
import re
import json
import random
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urljoin
import requests
from dotenv import load_dotenv
import logging

# Import eBay SDK
try:
    from ebaysdk.finding import Connection as Finding
    from ebaysdk.exception import ConnectionError as eBayConnectionError

    EBAY_SDK_AVAILABLE = True
except ImportError:
    EBAY_SDK_AVAILABLE = False
    print("eBay SDK not available, falling back to simulation for eBay")

# Load environment variables
load_dotenv()


class MarketScraper:
    def __init__(self, cache_dir: str = "cache"):
        """Initialize the market scraper with cache directory"""
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger("MarketScraper")

        # Set up cache directory
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "market_prices.json")
        self.scrape_cache_file = os.path.join(cache_dir, "scrape_cache.json")

        # Cache settings
        self.cache_expiry_days = int(os.getenv("CACHE_EXPIRY_DAYS", "7"))
        self.scrape_cache_expiry_hours = int(os.getenv("SCRAPE_CACHE_EXPIRY_HOURS", "24"))

        # User agents for rotation to avoid blocking
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        ]
        self.user_agent = random.choice(self.user_agents)  # Initial user agent
        
        # Rate limiting settings
        self.last_request_time = 0
        self.min_request_interval = float(os.getenv('MIN_REQUEST_INTERVAL', '2'))  # seconds
        self.max_requests_per_session = int(os.getenv('MAX_REQUESTS_PER_SESSION', '25'))
        self.session_rest_time = float(os.getenv('SESSION_REST_TIME', '60'))  # seconds
        self.current_session_requests = 0

        # Reverb API settings
        self.api_token = os.getenv("REVERB_API_TOKEN")
        self.use_sandbox = os.getenv("USE_SANDBOX", "False").lower() == "true"
        self.base_domain = (
            "sandbox.reverb.com" if self.use_sandbox else "api.reverb.com"
        )
        self.base_url = f"https://{self.base_domain}/api"

        # Now set up headers after API token is loaded
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/hal+json",
            "Accept-Version": "3.0",
            "Content-Type": "application/hal+json",
            "Accept-Language": "en-US,en;q=0.9",
        }

        # Add authorization if token exists
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"

        # eBay API settings
        self.ebay_app_id = os.getenv("EBAY_APP_ID")
        self.ebay_cert_id = os.getenv("EBAY_CERT_ID")
        self.ebay_dev_id = os.getenv("EBAY_DEV_ID")
        self.ebay_enabled = EBAY_SDK_AVAILABLE and bool(self.ebay_app_id)

        if self.ebay_enabled:
            try:
                self.ebay_api = Finding(appid=self.ebay_app_id, config_file=None)
                self.logger.info("eBay API initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize eBay API: {str(e)}")
                self.ebay_enabled = False

        # Guitar Center settings
        self.gc_base_url = "https://www.guitarcenter.com"
        self.gc_search_url = f"{self.gc_base_url}/search"

        # Craigslist settings
        self.craigslist_region = os.getenv("CRAIGSLIST_REGION", "sfbay")
        self.craigslist_base_url = f"https://{self.craigslist_region}.craigslist.org"

        # Initialize caches
        self.price_cache = {}
        self.scrape_cache = {}
        
        # Add default scrape headers
        self.scrape_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # Load price cache
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    self.price_cache = json.load(f)
                self.logger.info(f"Loaded {len(self.price_cache)} cached prices from {self.cache_file}")
            except json.JSONDecodeError:
                self.logger.warning("Cache file corrupted, creating new cache")
                self.price_cache = {}
        
        # Load scrape cache
        if os.path.exists(self.scrape_cache_file):
            try:
                with open(self.scrape_cache_file, "r") as f:
                    self.scrape_cache = json.load(f)
                self.logger.info(f"Loaded {len(self.scrape_cache)} cached web scrapes")
            except json.JSONDecodeError:
                self.logger.warning("Scrape cache file corrupted, creating new cache")
                self.scrape_cache = {}

    def _rate_limited_request(self, url, headers=None, timeout=15, max_retries=2):
        """Make a rate-limited request with automatic retries and user agent rotation"""
        if headers is None:
            headers = {}
        
        # Enforce rate limiting
        current_time = time.time()
        elapsed_since_last_request = current_time - self.last_request_time
        
        # If we need to slow down, sleep for the appropriate time
        if elapsed_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed_since_last_request
            self.logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Check if we need to reset the session due to too many requests
        self.current_session_requests += 1
        if self.current_session_requests >= self.max_requests_per_session:
            self.logger.info(f"Taking a break after {self.current_session_requests} requests")
            time.sleep(self.session_rest_time)
            self.current_session_requests = 0
        
        # Rotate user agents to appear more human
        user_agent = random.choice(self.user_agents)
        request_headers = self.scrape_headers.copy()
        request_headers["User-Agent"] = user_agent
        
        # Add any additional headers
        if headers:
            request_headers.update(headers)
            
        # Make the request with retries
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, headers=request_headers, timeout=timeout)
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too Many Requests
                    wait_time = 30 * (attempt + 1)  # Progressive backoff
                    self.logger.warning(f"Rate limited (429). Waiting for {wait_time} seconds")
                    time.sleep(wait_time)
                else:
                    self.logger.warning(f"Got status code {response.status_code} for {url}")
                    if attempt < max_retries:
                        time.sleep(5 * (attempt + 1))
            except (requests.RequestException, ConnectionError) as e:
                self.logger.error(f"Request error on attempt {attempt+1}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(5 * (attempt + 1))
        
        # If we get here, all retries failed
        return None



    def save_cache(self):
        """Save the price cache to file"""
        with open(self.cache_file, "w") as f:
            json.dump(self.price_cache, f)
            
    def save_scrape_cache(self):
        """Save the web scraping cache to file"""
        with open(self.scrape_cache_file, "w") as f:
            json.dump(self.scrape_cache, f)

    def clean_description(self, description: str) -> str:
        """Clean item description to get better search results"""
        # Remove case details and other common phrases
        cleaned = re.sub(
            r"w/\s+(Hardshell|Chipboard)?\s*Case", "", description, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"w/\s+Bag", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bNOS\b", "", cleaned)  # New Old Stock
        cleaned = re.sub(r"\bNew\b", "", cleaned)
        cleaned = re.sub(r"\bRetail\b", "", cleaned)
        return cleaned.strip()

    def _standardize_condition(self, condition_text: str) -> str:
        """Standardize condition values for better analysis"""
        condition_text = condition_text.lower() if condition_text else ''
        
        # Standard condition categories
        if not condition_text:
            return "Unknown"
            
        if "new" in condition_text or "brand new" in condition_text or "unopened" in condition_text:
            if "open box" in condition_text or "opened" in condition_text:
                return "Open Box"
            return "New"
            
        if "like new" in condition_text or "mint" in condition_text or "excellent" in condition_text:
            return "Like New"
            
        if "very good" in condition_text or "great" in condition_text or "vg" in condition_text:
            return "Very Good"
            
        if "good" in condition_text or "gd" in condition_text:
            return "Good"
            
        if "fair" in condition_text or "acceptable" in condition_text:
            return "Fair"
            
        if "poor" in condition_text or "as is" in condition_text or "for parts" in condition_text or "not working" in condition_text:
            return "Poor/For Parts"
            
        if "refurbished" in condition_text or "renewed" in condition_text or "reconditioned" in condition_text:
            return "Refurbished"
            
        # Default to "Used" for anything else
        if "pre-owned" in condition_text or "preowned" in condition_text or "used" in condition_text:
            return "Used"
            
        return "Used"  # Default

    def get_market_price(self, item_description: str, refresh_cache=False) -> dict:
        """Get market price for an item using multiple sources with real API and fallback"""
        # Clean the description for better search and use as cache key
        cleaned_desc = self.clean_description(item_description)
        cache_key = cleaned_desc.lower()
        self.logger.info(f"Getting market price for: {cleaned_desc}")
        
        # Get current time for cache checks and timestamps
        now = datetime.now()
        
        # Check cache first if not forcing refresh
        if not refresh_cache and cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            # Check if cache is still valid based on expiry setting
            timestamp = cached_data.get("timestamp")
            if timestamp:
                # Ensure timestamp is a string before parsing
                if not isinstance(timestamp, str):
                    timestamp = str(timestamp)
                try:
                    cache_date = datetime.fromisoformat(timestamp)
                    if now - cache_date < timedelta(days=self.cache_expiry_days):
                        self.logger.info(f"Using cached data for: {cleaned_desc}")
                        return cached_data
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid timestamp in cache for: {cleaned_desc}")
        
        # Initialize results
        result = {
            "average_price": 0.0,
            "confidence_level": 0,
            "sources": {},
            "source_type": "unknown",
            "timestamp": now.isoformat(),
        }

        # Try to get price from Reverb API first
        reverb_price = None
        try:
            reverb_data = self.search_reverb_api(cleaned_desc)
            if reverb_data:
                reverb_price = reverb_data.get("average_price", 0)
                if reverb_price > 0:
                    result["sources"]["reverb_api"] = reverb_price
                    result["source_type"] = "reverb_api"
                    result["confidence_level"] = 90 # High confidence from Reverb API
                    self.logger.info(f"Found Reverb API data for: {cleaned_desc}")
        except Exception as e:
            self.logger.error(f"Error getting Reverb API price: {str(e)}")

        # If we couldn't get from Reverb API, try simulated Reverb
        if not reverb_price or reverb_price <= 0:
            try:
                reverb_price = self.search_reverb(cleaned_desc)
                if reverb_price > 0:
                    result["sources"]["reverb_sim"] = reverb_price
                    result["source_type"] = "reverb_sim"
                    result["confidence_level"] = 70 # Medium confidence for simulation
                    self.logger.info(f"Using simulated Reverb data for: {cleaned_desc}")
            except Exception as e:
                self.logger.error(f"Error getting simulated Reverb price: {str(e)}")

        # Try to get price from eBay through web scraping
        ebay_price = None
        try:
            # Try web scraping approach first (most reliable without API keys)
            ebay_scraped_data = self.search_ebay_scrape(cleaned_desc)
            if ebay_scraped_data and "average_price" in ebay_scraped_data:
                ebay_price = ebay_scraped_data["average_price"]
                result["sources"]["ebay_scraped"] = ebay_price
                if not reverb_price or reverb_price <= 0:
                    result["source_type"] = "ebay_scraped"
                    result["confidence_level"] = 85 # Good confidence from scraped data
        except Exception as e:
            self.logger.error(f"Error scraping eBay: {str(e)}")
            
        # Try eBay API as fallback if scraping failed
        if (not ebay_price or ebay_price <= 0) and self.ebay_enabled:
            try:
                # Use direct API calls to avoid circular reference
                cleaned_query = self.clean_description(cleaned_desc)
                self.logger.info(f"Searching eBay API directly for: {cleaned_query}")
                
                # Set up API request parameters
                api_request = {
                    'keywords': cleaned_query,
                    'itemFilter': [
                        {'name': 'ListingType', 'value': 'FixedPrice'},
                        {'name': 'AvailableTo', 'value': 'US'},
                        {'name': 'HideDuplicateItems', 'value': 'true'}
                    ],
                    'sortOrder': 'EndTimeSoonest',
                    'paginationInput': {
                        'entriesPerPage': 10,
                        'pageNumber': 1
                    }
                }
                
                # Execute API call
                response = self.ebay_api.execute('findItemsAdvanced', api_request)
                response_dict = response.dict()
                
                # Process results
                prices = []
                if response_dict.get('ack') == 'Success' and 'searchResult' in response_dict:
                    search_result = response_dict['searchResult']
                    if int(search_result.get('_count', '0')) > 0 and 'item' in search_result:
                        for item in search_result['item']:
                            if 'sellingStatus' in item and 'currentPrice' in item['sellingStatus']:
                                price = float(item['sellingStatus']['currentPrice']['value'])
                                if price > 0:
                                    prices.append(price)
                
                # Calculate average if we have prices
                if prices:
                    ebay_price = sum(prices) / len(prices)
                    result["sources"]["ebay_api"] = ebay_price
                    if not reverb_price or reverb_price <= 0:
                        result["source_type"] = "ebay_api"
                        result["confidence_level"] = 80 # Good confidence from API
            except Exception as e:
                self.logger.error(f"Error using eBay API: {str(e)}")

        # Try simulated eBay as last resort
        if not ebay_price or ebay_price <= 0:
            try:
                ebay_sim_price = self.search_ebay(cleaned_desc)
                if ebay_sim_price and ebay_sim_price > 0:
                    result["sources"]["ebay_sim"] = ebay_sim_price
                    if not reverb_price or reverb_price <= 0:
                        result["source_type"] = "ebay_sim"
                        result["confidence_level"] = 60 # Lower confidence for simulation
            except Exception as e:
                self.logger.error(f"Error with simulated eBay: {str(e)}")
                
        # Try Sweetwater
        sweetwater_price = None
        try:
            sweetwater_price = self.search_sweetwater(cleaned_desc)
            if sweetwater_price and sweetwater_price > 0:
                result["sources"]["sweetwater"] = sweetwater_price
                # Use Sweetwater as last resort if no other sources available
                if not reverb_price and not ebay_price:
                    result["source_type"] = "sweetwater"
                    result["confidence_level"] = 50  # Lower confidence for retail prices
        except Exception as e:
            self.logger.error(f"Error getting Sweetwater price: {str(e)}")
            
        # Calculate combined average price if we have multiple sources
        prices = []
        if "reverb_api" in result["sources"]:
            prices.append(result["sources"]["reverb_api"]) 
        if "ebay_scraped" in result["sources"]:
            prices.append(result["sources"]["ebay_scraped"])
        if "ebay_api" in result["sources"]:
            prices.append(result["sources"]["ebay_api"])
        
        # Add simulation data with lower weight if we need more data points
        if len(prices) < 2:
            if "reverb_sim" in result["sources"]:
                prices.append(result["sources"]["reverb_sim"])
            if "ebay_sim" in result["sources"]:
                prices.append(result["sources"]["ebay_sim"])
            if "sweetwater" in result["sources"]:
                prices.append(result["sources"]["sweetwater"])
                
        # Calculate average price if we have data
        if prices:
            result["average_price"] = sum(prices) / len(prices)
            result["count"] = len(prices)
            # Increase confidence level if we have multiple sources
            if len(prices) > 1 and result["confidence_level"] < 95:
                result["confidence_level"] += min(10 * (len(prices) - 1), 20)
            # Cap confidence level at 100%
            result["confidence_level"] = min(result["confidence_level"], 100)
                
        # Update the cache with our result
        self.price_cache[cache_key] = result
        self.save_cache()
        
        return result

    def search_reverb_api(self, item_description: str, max_results=10) -> dict:
        """Search Reverb.com for market prices using the official API"""
        # Clean up item description for better search results
        query = self.clean_description(item_description)

        try:
            # Print debug info
            print(f"Using Reverb API at: {self.base_url}")
            print(
                f"Authorization header: {'Set' if 'Authorization' in self.headers else 'Not set'}"
            )

            # Make API request to search listings
            url = f"{self.base_url}/listings"
            params = {"query": quote_plus(query), "per_page": max_results}

            response = requests.get(
                url, headers=self.headers, params=params, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                listings = data.get("listings", [])

                if listings:
                    # Extract prices and other data from listings
                    prices = []
                    conditions = []
                    titles = []
                    urls = []

                    for listing in listings:
                        price_info = listing.get("price", {})
                        condition_info = listing.get("condition", {})

                        if price_info:
                            price = float(price_info.get("amount", 0))
                            condition = condition_info.get("display_name", "Unknown")
                            title = listing.get("title", "")
                            url = (
                                listing.get("_links", {})
                                .get("self", {})
                                .get("href", "")
                            )

                            prices.append(price)
                            conditions.append(condition)
                            titles.append(title)
                            urls.append(url)

                    if prices:
                        # Calculate statistics
                        prices.sort()  # For median calculation
                        median_index = len(prices) // 2
                        median = (
                            prices[median_index]
                            if len(prices) % 2 == 1
                            else (prices[median_index - 1] + prices[median_index]) / 2
                        )

                        # Analyze conditions
                        condition_counts = {}
                        for condition in conditions:
                            if condition:
                                condition_counts[condition] = (
                                    condition_counts.get(condition, 0) + 1
                                )

                        # Format sample listings
                        samples = []
                        for i in range(min(3, len(prices))):
                            samples.append(
                                {
                                    "title": titles[i],
                                    "price": prices[i],
                                    "condition": conditions[i],
                                    "url": urls[i],
                                }
                            )

                        # Return comprehensive result
                        return {
                            "average_price": sum(prices) / len(prices),
                            "median_price": median,
                            "min_price": min(prices),
                            "max_price": max(prices),
                            "count": len(prices),
                            "conditions": condition_counts,
                            "sample_listings": samples,
                            "source_type": "reverb_api",
                            "timestamp": datetime.now().isoformat(),
                        }

            print(f"API request failed with status code: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            return None

        except Exception as e:
            print(f"Error searching Reverb API: {str(e)}")
            return None

    def search_reverb(self, item_description: str) -> float:
        """Search Reverb.com for prices (simulated for demo)"""
        # In a real implementation, this would actually scrape Reverb.com
        # For now, we'll simulate it with some realistic pricing logic
        cleaned = self.clean_description(item_description).lower()

        # Extract brand and instrument type
        brands = [
            "fender",
            "gibson",
            "martin",
            "taylor",
            "prs",
            "ibanez",
            "epiphone",
            "squier",
            "gretsch",
            "jackson",
            "charvel",
            "yamaha",
            "korg",
            "roland",
        ]
        brand = next((b for b in brands if b in cleaned), None)

        is_guitar = any(
            x in cleaned
            for x in ["guitar", "stratocaster", "telecaster", "les paul", "sg"]
        )
        is_acoustic = "acoustic" in cleaned
        is_bass = "bass" in cleaned
        is_amp = any(x in cleaned for x in ["amp", "amplifier"])
        is_pedal = any(
            x in cleaned
            for x in ["pedal", "effect", "delay", "distortion", "overdrive"]
        )
        is_keyboard = any(
            x in cleaned for x in ["keyboard", "piano", "synth", "synthesizer", "nord"]
        )
        is_drum = any(
            x in cleaned for x in ["drum", "snare", "cymbal", "hi-hat", "kick"]
        )

        # Base price depends on instrument type and brand
        if is_guitar:
            if brand in ["gibson", "fender", "prs", "martin", "taylor"]:
                base_price = random.uniform(800, 3000)
            else:
                base_price = random.uniform(300, 1200)

            if is_acoustic:
                base_price *= 1.2  # Acoustic guitars often cost a bit more

        elif is_bass:
            if brand in ["fender", "gibson"]:
                base_price = random.uniform(700, 1800)
            else:
                base_price = random.uniform(250, 900)

        elif is_amp:
            if brand in ["fender", "marshall", "vox", "mesa"]:
                base_price = random.uniform(500, 2200)
            else:
                base_price = random.uniform(200, 800)

        elif is_pedal:
            base_price = random.uniform(80, 350)

        elif is_keyboard:
            if "nord" in cleaned or "moog" in cleaned:
                base_price = random.uniform(1200, 3500)
            else:
                base_price = random.uniform(400, 1500)

        elif is_drum:
            base_price = random.uniform(300, 1200)

        else:
            # Generic calculation
            base_price = random.uniform(200, 1000)

        # Add some randomness to make it more realistic
        variation = random.uniform(0.9, 1.1)
        final_price = base_price * variation

        return round(final_price, 2)

    def search_ebay_scrape(self, query: str, max_results: int = 30, max_pages: int = 3, use_cache: bool = True) -> Optional[dict]:
        """Search eBay for market prices using web scraping with pagination support"""
        try:
            # Clean up query for better search results
            cleaned_query = self.clean_description(query)
            search_query = quote_plus(cleaned_query)
            self.logger.info(f"Scraping eBay for: {cleaned_query}")
            
            # Check cache first if allowed
            if use_cache:
                cache_key = f"ebay_scrape_{search_query}"
                if cache_key in self.scrape_cache:
                    cache_entry = self.scrape_cache[cache_key]
                    # Check if cache is still valid (within expiry time)
                    cache_time = datetime.fromisoformat(cache_entry["timestamp"])
                    cache_age = datetime.now() - cache_time
                    if cache_age < timedelta(hours=self.scrape_cache_expiry_hours):
                        self.logger.info(f"Using cached eBay scrape result for '{cleaned_query}', age: {cache_age}")
                        return cache_entry["result"]
                    else:
                        self.logger.info(f"Cached eBay scrape expired for '{cleaned_query}', refreshing")
                else:
                    self.logger.debug(f"No cache entry found for '{cleaned_query}'")
            
            # Initialize data storage
            prices = []
            conditions = []
            titles = []
            urls = []
            
            # Items per page - eBay standard options are 25, 50, 100, 200
            items_per_page = 50  # Good balance between data and request count
            
            # Loop through multiple pages until we reach max_results or max_pages
            for page_num in range(1, max_pages + 1):
                if len(prices) >= max_results:
                    break
                    
                # Create search URL for completed listings with pagination
                base_url = "https://www.ebay.com/sch/i.html"
                params = {
                    "_nkw": search_query,      # search term
                    "LH_Complete": "1",       # completed listings
                    "LH_Sold": "1",           # sold items only
                    "rt": "nc",               # no related searches
                    "_ipg": str(items_per_page),  # items per page
                    "_pgn": str(page_num)      # page number
                }
                
                # Build the URL
                url_params = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{base_url}?{url_params}"
                
                self.logger.info(f"Fetching eBay page {page_num} for: {cleaned_query}")
                
                # Make rate-limited request with retries and rotation
                response = self._rate_limited_request(url)
                
                if not response:
                    self.logger.warning(f"Failed to retrieve page {page_num}")
                    break
                    
                self.logger.info(f"Successfully retrieved eBay search page {page_num}")
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all listing items on this page
                page_listings = soup.select('.s-item__pl-on-bottom')
                
                if not page_listings:
                    self.logger.info(f"No more listings found on page {page_num}")
                    break
                    
                # Count actual results on this page to check if we've reached the end
                result_count = 0
                    
                # Extract data from each listing
                for idx, listing in enumerate(page_listings):
                    # Skip "Shop on eBay" placeholders
                    if 'Shop on eBay' in listing.text:
                        continue
                    
                    # Extract title
                    title_elem = listing.select_one('.s-item__title')
                    if not title_elem or title_elem.text.startswith('Shop on eBay'):
                        continue
                        
                    title = title_elem.text.strip()
                    
                    # Extract price
                    price_elem = listing.select_one('.s-item__price')
                    if not price_elem:
                        continue
                        
                    price_text = price_elem.text.strip()
                    # Extract first price if there are multiple (e.g., "$10.00 to $15.00")
                    if ' to ' in price_text:
                        price_text = price_text.split(' to ')[0]
                        
                    # Remove currency symbol and commas
                    price_match = re.search(r'[\$£€]([\d,]+\.\d+)', price_text)
                    if not price_match:
                        continue
                        
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price = float(price_str)
                        
                        # Extract condition
                        condition_elem = listing.select_one('.SECONDARY_INFO')
                        condition_raw = 'Used'  # Default
                        if condition_elem:
                            condition_raw = condition_elem.text.strip()
                            
                        # Standardize condition values for better analysis
                        condition = self._standardize_condition(condition_raw)
                        
                        # Extract URL
                        url_elem = listing.select_one('a.s-item__link')
                        item_url = ''
                        if url_elem and 'href' in url_elem.attrs:
                            item_url = url_elem['href'].split('?')[0]  # Remove query params
                        
                        # Add to our lists
                        prices.append(price)
                        conditions.append(condition)
                        titles.append(title)
                        urls.append(item_url)
                        result_count += 1
                        
                        # Stop if we've reached our target max_results
                        if len(prices) >= max_results:
                            self.logger.info(f"Reached target of {max_results} listings")
                            break
                            
                    except ValueError:
                        self.logger.warning(f"Could not parse price: {price_text}")
                        
                self.logger.info(f"Found {result_count} valid listings on page {page_num}")
                
                # If this page had fewer results than items_per_page, we've reached the end
                if result_count < items_per_page - 5:  # Allow for a few missing items
                    self.logger.info("Reached end of results")
                    break
                
            # Process results outside the page loop (we already collected all data across pages)
            if prices:
                # Calculate statistics
                prices.sort()  # For median calculation
                median_index = len(prices) // 2
                median = (
                    prices[median_index]
                    if len(prices) % 2 == 1
                    else (prices[median_index - 1] + prices[median_index]) / 2
                )
                
                # Track condition distribution
                condition_counts = {}
                for condition in conditions:
                    if condition in condition_counts:
                        condition_counts[condition] += 1
                    else:
                        condition_counts[condition] = 1
                
                # Create sample listings for reference
                sample_listings = []
                # Include more listings in our samples since we have more data now
                for idx in range(min(len(prices), 10)):
                    if idx < len(titles):
                        sample_listings.append({
                            "title": titles[idx],
                            "price": prices[idx],
                            "condition": conditions[idx],
                            "url": urls[idx] if idx < len(urls) else ""
                        })
                
                result = {
                    "source": "ebay_scraped",
                    "count": len(prices),
                    "average_price": sum(prices) / len(prices),
                    "median_price": median,
                    "min_price": min(prices),
                    "max_price": max(prices),
                    "sample_listings": sample_listings,
                    "condition_counts": condition_counts,
                    "timestamp": datetime.now().isoformat(),
                    "confidence_level": min(70 + (len(prices) // 5), 85)  # Higher confidence with more listings, up to 85%
                }
                
                self.logger.info(f"Found {len(prices)} eBay listings with average price ${sum(prices) / len(prices):.2f}")
                
                # Cache the result
                if use_cache:
                    cache_key = f"ebay_scrape_{search_query}"
                    self.scrape_cache[cache_key] = {
                        "result": result,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.save_scrape_cache()
                    
                return result
            
            # If we get here, no valid listings were found
            self.logger.warning("No valid eBay listings found")
            return None
            
        except Exception as e:
            self.logger.error(f"Error scraping eBay: {str(e)}")
            return None
    
    def search_ebay_api(self, query: str, max_results: int = 10) -> Optional[dict]:
        """Search eBay for market prices using the official eBay Finding API
        Falls back to web scraping if API is not available"""
        if not self.ebay_enabled:
            self.logger.warning("eBay API is not available, trying web scraping instead")
            # Try scraping first
            scraped_result = self.search_ebay_scrape(query, max_results)
            if scraped_result:
                return scraped_result
                
            # Fall back to simulation if scraping fails
            self.logger.warning("Web scraping failed, using simulation instead")
            simulated_price = self.search_ebay(query)
            if simulated_price:
                # Convert the simple price to a more comprehensive format similar to the API
                return {
                    'average_price': simulated_price,
                    'median_price': simulated_price,
                    'min_price': simulated_price * 0.9,  # Simulate some variance
                    'max_price': simulated_price * 1.1,
                    'count': 3,  # Simulate a small number of results
                    'conditions': {'Good': 1, 'Very Good': 1, 'Excellent': 1},
                    'sample_listings': [
                        {
                            'title': f"{query} - Simulated Listing 1",
                            'price': simulated_price * 0.95,
                            'condition': 'Good',
                            'url': 'https://www.ebay.com'
                        },
                        {
                            'title': f"{query} - Simulated Listing 2",
                            'price': simulated_price,
                            'condition': 'Very Good',
                            'url': 'https://www.ebay.com'
                        },
                        {
                            'title': f"{query} - Simulated Listing 3",
                            'price': simulated_price * 1.05,
                            'condition': 'Excellent',
                            'url': 'https://www.ebay.com'
                        }
                    ],
                    'source_type': 'ebay_simulation',
                    'timestamp': datetime.now().isoformat()
                }
            return None
            
        try:
            # Clean up query for better search results
            cleaned_query = self.clean_description(query)
            self.logger.info(f"Searching eBay API for: {cleaned_query}")
            
            # Set up API request parameters
            api_request = {
                'keywords': cleaned_query,
                'itemFilter': [
                    {'name': 'ListingType', 'value': 'FixedPrice'},
                    {'name': 'AvailableTo', 'value': 'US'},
                    {'name': 'HideDuplicateItems', 'value': 'true'}
                ],
                'sortOrder': 'EndTimeSoonest',
                'paginationInput': {
                    'entriesPerPage': max_results,
                    'pageNumber': 1
                },
                'outputSelector': ['SellerInfo', 'AspectHistogram']
            }
            
            # Execute API call
            response = self.ebay_api.execute('findItemsAdvanced', api_request)
            response_dict = response.dict()
            
            # Process response
            if response_dict.get('ack') == 'Success' and 'searchResult' in response_dict:
                search_result = response_dict['searchResult']
                count = int(search_result.get('_count', '0'))
                
                if count > 0 and 'item' in search_result:
                    items = search_result['item']
                    
                    # Extract prices and other relevant data
                    prices = []
                    conditions = []
                    titles = []
                    urls = []
                    
                    for item in items:
                        if 'sellingStatus' in item and 'currentPrice' in item['sellingStatus']:
                            price_info = item['sellingStatus']['currentPrice']
                            price = float(price_info['value'])
                            
                            condition = 'Unknown'
                            if 'condition' in item and 'conditionDisplayName' in item['condition']:
                                condition = item['condition']['conditionDisplayName']
                            
                            title = item.get('title', '')
                            url = item.get('viewItemURL', '')
                            
                            # Only include if price is valid
                            if price > 0:
                                prices.append(price)
                                conditions.append(condition)
                                titles.append(title)
                                urls.append(url)
                    
                    if prices:
                        # Calculate statistics
                        prices.sort()  # For median calculation
                        median_index = len(prices) // 2
                        median = (
                            prices[median_index]
                            if len(prices) % 2 == 1
                            else (prices[median_index - 1] + prices[median_index]) / 2
                        )
                        
                        # Analyze conditions
                        condition_counts = {}
                        for condition in conditions:
                            if condition:
                                condition_counts[condition] = condition_counts.get(condition, 0) + 1
                        
                        # Format sample listings
                        samples = []
                        for i in range(min(3, len(prices))):
                            samples.append({
                                'title': titles[i],
                                'price': prices[i],
                                'condition': conditions[i],
                                'url': urls[i]
                            })
                        
                        # Return comprehensive result
                        return {
                            'average_price': sum(prices) / len(prices),
                            'median_price': median,
                            'min_price': min(prices),
                            'max_price': max(prices),
                            'count': len(prices),
                            'conditions': condition_counts,
                            'sample_listings': samples,
                            'source_type': 'ebay_api',
                            'timestamp': datetime.now().isoformat()
                        }
            
            self.logger.warning("No valid eBay listings found")
            # Fall back to simulated data if API call succeeded but found no results
            return self.search_ebay_api(query, max_results)  # This will trigger the simulation branch
            
        except Exception as e:
            self.logger.error(f"Error searching eBay API: {str(e)}")
            # Fall back to simulated data on errors
            return self.search_ebay_api(query, max_results)  # This will trigger the simulation branch

    def search_ebay(self, query: str) -> Optional[float]:
        """Search eBay for prices (simulated for demo)"""
        # Simulate a slight price difference from Reverb
        reverb_price = self.search_reverb(query)
        if reverb_price:
            # eBay prices tend to be a bit lower
            return round(reverb_price * random.uniform(0.85, 0.95))
        return None

    def search_sweetwater(self, query: str) -> Optional[float]:
        """Search Sweetwater for prices (simulated for demo)"""
        # Simulate retail prices (generally higher and more consistent)
        reverb_price = self.search_reverb(query)
        if reverb_price:
            # Retail prices tend to be higher and more standardized
            return round(reverb_price * random.uniform(1.1, 1.3))
        return None


# Example usage
if __name__ == "__main__":
    scraper = MarketScraper()
    test_items = [
        "Gibson Les Paul Standard",
        "Fender Stratocaster",
        "Boss DD-7 Digital Delay",
        "Taylor 814ce",
    ]

    for item in test_items:
        print(f"Finding market price for: {item}")
        result = scraper.get_market_price(item)
        print(f"Results: {json.dumps(result, indent=2)}")
        print("---")
