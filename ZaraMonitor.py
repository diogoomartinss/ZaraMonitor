import aiohttp
import json
import urllib
import logging
import asyncio

logger = logging.getLogger('monitor')

class ZaraMonitor:
    def __init__(self, URL, product_name):
        self.interval = 2
        self.current_stock = {}
        self.previous_stock = {}
        self.URL = URL
        self.product_id = self.extract_product_id(URL)
        self.country_id = self.get_store_ID()
        self.stock_URL = f"https://www.zara.com/itxrest/1/catalog/store/{self.country_id}/product/id/{self.product_id}/availability"
        self.session = None
        self._session_lock = asyncio.Lock()
        self.size_mapping = {} 
        self.product_name = product_name

    def get_store_ID(self):
        with open("config.json", "r") as f:
            config = json.load(f)

        return config['country_id']

    def extract_product_id(self, url):
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        return query_params.get('v1', [None])[0]
    
    async def ensure_session(self):
        async with self._session_lock:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()

    async def initialize(self):
        """Initialize the monitor by fetching and storing the SKU-size mapping."""
        await self.ensure_session()
        await self._fetch_size_mapping()

    async def _fetch_size_mapping(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.zara.com/pt/pt/vestido-midi-acetinado-p02452331.html?v1=431706812"
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.url) as response:
                    response.raise_for_status()
                    data = await response.json()

            products = data.get('recommendations', [])

            for product in products:
                if product['fullResponse']['name'] == self.product_name:
                    colors = product['fullResponse']['detail']['colors']

                    sku_to_size_map = {}
                    for color in colors:
                        for size in color['sizes']:
                            sku = size['sku']
                            size_name = size['name']
                            sku_to_size_map[sku] = size_name

                    return sku_to_size_map

            print(f"Product '{self.product_name}' not found.")
            return None

        except aiohttp.ClientResponseError as e:
            print(f"Request Error: {e}")
            return None
        except aiohttp.ClientError as e:
            print(f"Client Error: {e}")
            return None
        except json.JSONDecodeError:
            print("Error: Invalid JSON format.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

    async def check_stock(self):
        await self.ensure_session()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.URL
        }

        try:
            logger.info(f"Checking stock for product ID: {self.product_id} at URL: {self.stock_URL}")
            async with self.session.get(self.stock_URL, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Error: Received status code {response.status} for URL {self.stock_URL}")
                    return False
                
                data = await response.json()
                logger.info(f"Stock API Response: {json.dumps(data)}")

                skus_availability = data.get("skusAvailability", [])
                if not isinstance(skus_availability, list):
                    logger.error(f"Error: Expected list for skusAvailability, got {type(skus_availability)}")
                    return False

                self.previous_stock = self.current_stock.copy()
                self.current_stock = {}
                
                for item in skus_availability:
                    sku = str(item.get("sku", "unknown"))
                    availability = item.get("availability")
                    logger.info(f"Processing SKU {sku} with availability: {availability}")
                    if sku != "unknown" and availability:
                        self.current_stock[sku] = availability

                in_stock = False
                for sku, status in self.current_stock.items():
                    logger.info(f"Checking SKU {sku} with status {status}")
                    if status in ["in_stock", "low_on_stock"]:
                        in_stock = True
                        break

                logger.info(f"Current stock status: {self.current_stock}")
                logger.info(f"Final in_stock status: {in_stock}")
                return in_stock
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error checking stock for URL {self.stock_URL}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking stock for URL {self.stock_URL}: {e}")
            return False

    def has_stock_changed(self):
        if not self.previous_stock:
            return True
        return self.current_stock != self.previous_stock

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def get_sku_size_mapping(self):
        if not self.size_mapping:
            await self._fetch_size_mapping()
        return self.size_mapping.copy()

    async def check_loop(self):
        while True:
            in_stock = self.check_stock()
            if self.has_stock_changed():
                print(f'Item  {self.item_name} in stock!')
                await asyncio.sleep(3)
            await asyncio.sleep(self.interval)