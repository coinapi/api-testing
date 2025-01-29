import requests
import websockets
import asyncio
import json
import time
from datetime import datetime, timedelta
import logging
import csv
import socket
import dns.resolver
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
CONFIG = {
    "API_KEY": "45ad618a-fa41-4271-ae57-a75a3bcb6ce9",  # Replace with your API key
    "BASE_URL_REALTIME": "https://api-realtime.exrates.coinapi.io/v1",
    "BASE_URL_HISTORICAL": "https://api-historical.exrates.coinapi.io/v1",
    "WS_URL": "wss://api-realtime.exrates.coinapi.io",
    "JSONRPC_URL_REALTIME": "https://api-realtime.exrates.coinapi.io/jsonrpc",
    "JSONRPC_URL_HISTORICAL": "https://api-historical.exrates.coinapi.io/jsonrpc",
    
    # Test parameters
    "TEST_ASSET_BASE": "BTC",
    "TEST_ASSET_QUOTE": "USD",
    "TIME_START": "2025-01-20T00:00:00",
    "TIME_END": "2025-01-23T00:00:00",
    "PERIOD_ID": "1HRS",
    "WS_TEST_DURATION": 300,  # 5 minutes in seconds
    "OUTPUT_DIR": "api_test_results",
    "REQUEST_TIMEOUT": 240,
    "MAX_RETRIES": 5
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class APITester:
    def __init__(self, config):
        self.config = config
        self.headers = {
            "X-CoinAPI-Key": config["API_KEY"],
            "Accept": "application/json",
            "Accept-Encoding": "gzip"
        }
        self.results = {}
        self.session = self._setup_session()
        os.makedirs(self.config["OUTPUT_DIR"], exist_ok=True)

    def _setup_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config["MAX_RETRIES"],
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update(self.headers)
        return session

    def log_request(self, endpoint_name, url, method, start_time, response, latency):
        if endpoint_name not in self.results:
            self.results[endpoint_name] = []
            
        result = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "method": method,
            "latency_ms": latency,
            "status_code": response.status_code if hasattr(response, 'status_code') else None,
            "response_size": len(response.text) if hasattr(response, 'text') else len(str(response)),
            "response": response.json() if hasattr(response, 'json') else str(response)
        }
        self.results[endpoint_name].append(result)
        logger.info(f"Tested {endpoint_name} - Latency: {latency:.2f}ms - Status: {result['status_code']}")

    def test_endpoint(self, endpoint_name, url, method="GET", params=None, data=None, headers=None):
        start_time = time.perf_counter()
        try:
            request_headers = headers if headers else self.headers
            
            if method == "GET":
                response = self.session.get(
                    url, 
                    params=params,
                    headers=request_headers,
                    timeout=self.config["REQUEST_TIMEOUT"]
                )
            else:
                response = self.session.post(
                    url, 
                    json=data,
                    headers=request_headers,
                    timeout=self.config["REQUEST_TIMEOUT"]
                )
            
            latency = (time.perf_counter() - start_time) * 1000
            
            self.log_request(endpoint_name, url, method, start_time, response, latency)
            
            if response.status_code >= 400:
                logger.error(f"Error response from {url}: Status {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return None
                
            return response
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error for {url} after {self.config['REQUEST_TIMEOUT']} seconds")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {url}: {str(e)}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error testing {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error testing {url}: {str(e)}")
            return None

    def test_rest_endpoints(self):
        """Test all REST endpoints"""
        
        # Realtime API Endpoints
        realtime_endpoints = {
            "realtime_specific_rate": {
                "url": f"{self.config['BASE_URL_REALTIME']}/exchangerate/{self.config['TEST_ASSET_BASE']}/{self.config['TEST_ASSET_QUOTE']}"
            },
            "realtime_all_rates": {
                "url": f"{self.config['BASE_URL_REALTIME']}/exchangerate/{self.config['TEST_ASSET_BASE']}",
                "params": {
                    "filter_asset_id": self.config['TEST_ASSET_QUOTE'],
                    "time": self.config['TIME_START']
                }
            },
            "realtime_assets_list": {
                "url": f"{self.config['BASE_URL_REALTIME']}/assets"
            },
            "realtime_specific_asset": {
                "url": f"{self.config['BASE_URL_REALTIME']}/assets/{self.config['TEST_ASSET_BASE']}"
            },
            "realtime_asset_icons": {
                "url": f"{self.config['BASE_URL_REALTIME']}/assets/icons/32"
            }
        }
        
        # Historical API Endpoints
        historical_endpoints = {
            "historical_specific_rate": {
                "url": f"{self.config['BASE_URL_HISTORICAL']}/exchangerate/{self.config['TEST_ASSET_BASE']}/{self.config['TEST_ASSET_QUOTE']}",
                "params": {"time": self.config['TIME_START']}
            },
            "historical_all_rates": {
                "url": f"{self.config['BASE_URL_HISTORICAL']}/exchangerate/{self.config['TEST_ASSET_BASE']}",
                "params": {
                    "time": self.config['TIME_START'],
                    "filter_asset_id": self.config['TEST_ASSET_QUOTE']
                }
            },
            "historical_periods": {
                "url": f"{self.config['BASE_URL_HISTORICAL']}/exchangerate/history/periods"
            },
            "historical_timeseries": {
                "url": f"{self.config['BASE_URL_HISTORICAL']}/exchangerate/{self.config['TEST_ASSET_BASE']}/{self.config['TEST_ASSET_QUOTE']}/history",
                "params": {
                    "period_id": self.config['PERIOD_ID'],
                    "time_start": self.config['TIME_START'],
                    "time_end": self.config['TIME_END'],
                    "limit": 100
                }
            }
        }
        
        logger.info("Testing Realtime API endpoints...")
        for name, endpoint in realtime_endpoints.items():
            try:
                response = self.test_endpoint(
                    name, 
                    endpoint['url'], 
                    params=endpoint.get('params')
                )
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error testing {name}: {str(e)}")
                continue
        
        logger.info("Testing Historical API endpoints...")
        for name, endpoint in historical_endpoints.items():
            try:
                response = self.test_endpoint(
                    name,
                    endpoint['url'],
                    params=endpoint.get('params')
                )
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error testing {name}: {str(e)}")
                continue

    def test_jsonrpc(self):
        """Test JSON-RPC endpoints"""
        # Create headers correctly by creating a new dictionary
        jsonrpc_headers = self.headers.copy()  # Create a copy of existing headers
        jsonrpc_headers["Content-Type"] = "application/json"  # Add the new header
        
        rpc_requests = {
            "jsonrpc_realtime_rate": {
                "url": self.config['JSONRPC_URL_REALTIME'],
                "data": {
                    "jsonrpc": "2.0",
                    "id": "test-001",
                    "method": "v1/getCurrentExchangeRates",
                    "params": [
                        {"asset_id_base": self.config['TEST_ASSET_BASE']},
                        {"asset_id_quote": self.config['TEST_ASSET_QUOTE']}
                    ]
                }
            },
            "jsonrpc_historical_rate": {
                "url": self.config['JSONRPC_URL_HISTORICAL'],
                "data": {
                    "jsonrpc": "2.0",
                    "id": "test-002",
                    "method": "v1/getHistoricalExchangeRates",
                    "params": [
                        {"asset_id_base": self.config['TEST_ASSET_BASE']},
                        {"asset_id_quote": self.config['TEST_ASSET_QUOTE']},
                        {"period_id": self.config['PERIOD_ID']},
                        {"time_start": self.config['TIME_START']},
                        {"time_end": self.config['TIME_END']}
                    ]
                }
            }
        }
        
        logger.info("Testing JSON-RPC endpoints...")
        for name, request in rpc_requests.items():
            try:
                start_time = time.perf_counter()
                response = self.session.post(
                    request['url'],
                    headers=jsonrpc_headers,
                    json=request['data'],
                    timeout=self.config["REQUEST_TIMEOUT"]
                )
                
                latency = (time.perf_counter() - start_time) * 1000
                self.log_request(name, request['url'], "POST", start_time, response, latency)
                
                # Log the actual request and response for debugging
                logger.info(f"JSON-RPC Request {name}:")
                logger.info(json.dumps(request['data'], indent=2))
                logger.info(f"JSON-RPC Response {name}:")
                logger.info(response.text)
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in JSON-RPC request {name}: {str(e)}")
                continue

    async def test_websocket(self):
        """Test WebSocket connection"""
        logger.info("Starting WebSocket test...")
        ws_updates = []
        
        try:
            ws_url = f"{self.config['WS_URL']}/apikey-{self.config['API_KEY']}"
            connection_start = time.perf_counter()
            async with websockets.connect(
                ws_url,
                ping_interval=20
            ) as websocket:
                connection_latency = (time.perf_counter() - connection_start) * 1000
                logger.info(f"WebSocket connection established. Latency: {connection_latency:.2f}ms")
                # Construct asset pair with exact format
                asset_pair = f"{self.config['TEST_ASSET_BASE']}/{self.config['TEST_ASSET_QUOTE']}"
                
                subscribe_msg = {
                    "type": "hello",
                    "heartbeat": False,
                    "subscribe_filter_asset_id": [asset_pair]
                }
                
                start_time = time.time()
                
                # Log the subscription message for debugging
                logger.info("Sending WebSocket subscription message:")
                logger.info(json.dumps(subscribe_msg, indent=2))
                
                await websocket.send(json.dumps(subscribe_msg))
                logger.info("WebSocket subscription message sent")
                
                # Wait for initial connection acknowledgment
                try:
                    ack_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    logger.info(f"Connection acknowledgment: {ack_message}")
                except asyncio.TimeoutError:
                    logger.error("No acknowledgment received from WebSocket server")
                    return ws_updates
                
                while time.time() - start_time < self.config['WS_TEST_DURATION']:
                    try:
                        message_receive_start = time.perf_counter()
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        message_latency = (time.perf_counter() - message_receive_start) * 1000
                        update_time = time.time()
                        parsed_message = json.loads(message)
                        ws_updates.append({
                             "timestamp": update_time,
                             "message": parsed_message,
                             "latency_ms": message_latency
                             })
                        logger.info(f"WebSocket message received. Latency: {message_latency:.2f}ms")
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"Error receiving WebSocket message: {str(e)}")
                        break
                
                # Send a proper close frame
                try:
                    await websocket.close()
                    logger.info("WebSocket connection closed properly")
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {str(e)}")
                
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
        
        if ws_updates:
            self.save_websocket_results(ws_updates)
        
        return ws_updates

    def save_websocket_results(self, ws_updates):
        """Save WebSocket results to a separate file"""
        if not ws_updates:
            return
        
        # Calculate latency statistics
        latencies = [update.get("latency_ms", 0) for update in ws_updates]
        latency_stats = {
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "avg_latency_ms": sum(latencies)/len(latencies) if latencies else 0
    }
        ws_output = {
            "total_messages": len(ws_updates),
            "test_duration": self.config['WS_TEST_DURATION'],
            "latency_statistics": latency_stats,
            "messages": ws_updates
    }
        output_path = os.path.join(self.config["OUTPUT_DIR"], "websocket_results.json")
        with open(output_path, 'w') as f:
            json.dump(ws_output, f, indent=2)
        logger.info(f"WebSocket results saved to {output_path}")

    def save_results(self):
        """Save test results to separate CSV files per endpoint"""
        if not self.results:
            logger.warning("No results to save")
            return
            
        for endpoint_name, endpoint_results in self.results.items():
            if not endpoint_results:
                continue
                
            json_path = os.path.join(self.config["OUTPUT_DIR"], f"{endpoint_name}_results.json")
            with open(json_path, 'w') as f:
                json.dump(endpoint_results, f, indent=2)
            
            csv_path = os.path.join(self.config["OUTPUT_DIR"], f"{endpoint_name}_summary.csv")
            with open(csv_path, 'w', newline='') as f:
                summary_results = [{
                    "timestamp": r["timestamp"],
                    "url": r["url"],
                    "method": r["method"],
                    "latency_ms": r["latency_ms"],
                    "status_code": r["status_code"],
                    "response_size": r["response_size"]
                } for r in endpoint_results]
                
                writer = csv.DictWriter(f, fieldnames=summary_results[0].keys())
                writer.writeheader()
                writer.writerows(summary_results)
                
            logger.info(f"Results for {endpoint_name} saved to {json_path} and {csv_path}")

async def main():
    tester = APITester(CONFIG)
    
    # Test REST endpoints
    logger.info("Testing REST endpoints...")
    try:
        tester.test_rest_endpoints()
    except Exception as e:
        logger.error(f"Error in REST endpoints testing: {str(e)}")
    
    # Test JSON-RPC
    logger.info("Testing JSON-RPC endpoints...")
    try:
        tester.test_jsonrpc()
    except Exception as e:
        logger.error(f"Error in JSON-RPC testing: {str(e)}")
    
    # Test WebSocket
    logger.info("Testing WebSocket connection...")
    try:
        ws_results = await tester.test_websocket()
    except Exception as e:
        logger.error(f"Error in WebSocket testing: {str(e)}")
    
    # Save results regardless of any previous errors
    try:
        tester.save_results()
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}")
    
    logger.info("Testing completed. Check logs for any errors.")

if __name__ == "__main__":
    asyncio.run(main())