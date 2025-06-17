# your_trading_dashboard/market_data.py

import pandas as pd
from twelvedata import TDClient
from collections import deque
import asyncio
import logging

from config import TWELVEDATA_API_KEY, SYMBOL, INTERVAL, OHLCV_HISTORY_SIZE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarketDataStreamer:
    def __init__(self, symbol: str, interval: str, api_key: str, history_size: int):
        self.symbol = symbol
        self.interval = interval
        self.td = TDClient(apikey=api_key)
        
        self.ohlcv_history = deque(maxlen=history_size)
        self.current_price = None 

        self._ws_connection = None 

    async def fetch_initial_historical_data(self):
        """
        Fetches initial historical OHLCV data using REST API.
        """
        logging.info(f"Fetching initial {self.symbol} historical data ({self.interval})...")
        try:
            ts_data = self.td.time_series(
                symbol=self.symbol,
                interval=self.interval,
                outputsize=self.ohlcv_history.maxlen,
                timezone="exchange"
            ).as_json()

            if not ts_data or 'values' not in ts_data:
                logging.error("No initial historical data received or 'values' key missing.")
                return False

            df = pd.DataFrame(ts_data['values'])
            df = df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime').sort_index()

            for _, row in df.iterrows():
                self.ohlcv_history.append({
                    'timestamp': row.name.isoformat(),
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'] if 'volume' in row else 0
                })
            logging.info(f"Initial OHLCV history populated with {len(self.ohlcv_history)} bars.")
            return True

        except Exception as e:
            logging.error(f"Error fetching initial historical data: {e}")
            return False

    def get_ohlcv_dataframe(self) -> pd.DataFrame:
        """
        Converts the current OHLCV history (deque) into a Pandas DataFrame.
        """
        if not self.ohlcv_history:
            return pd.DataFrame()

        df = pd.DataFrame(list(self.ohlcv_history))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp').sort_index()
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df

    async def _on_event(self, event):
        """
        Internal callback function for Twelvedata WebSocket events.
        """
        if event['event'] == 'price':
            self.current_price = {
                'symbol': event['symbol'],
                'price': float(event['price']),
                'timestamp': event['timestamp']
            }
        elif event['event'] == 'ohlc':
            ohlc_data = {
                'timestamp': event['timestamp'],
                'open': float(event['open']),
                'high': float(event['high']),
                'low': float(event['low']),
                'close': float(event['close']),
                'volume': float(event['volume']) if 'volume' in event else 0
            }
            self.ohlcv_history.append(ohlc_data)
            logging.info(f"New OHLC bar received for {self.symbol} ({self.interval}): Close={ohlc_data['close']}")

        elif event['event'] == 'heartbeat':
            pass 

        elif event['event'] == 'subscribe-status':
            logging.info(f"WebSocket Subscription Status: {event}")
            if event.get('status') == 'error':
                logging.error(f"Twelvedata WebSocket subscription error: {event.get('message')}")

        else:
            logging.debug(f"Received other WebSocket event: {event}")

    async def start_websocket(self):
        """
        Connects to the Twelvedata WebSocket for real-time streaming.
        """
        if self._ws_connection:
            await self.stop_websocket()

        logging.info(f"Connecting to Twelvedata WebSocket for {self.symbol} ({self.interval})...")
        try:
            self._ws_connection = self.td.websocket(
                symbols=[self.symbol],
                on_event=self._on_event,
                intervals=[self.interval]
            )
            await self._ws_connection.connect()
            logging.info("Twelvedata WebSocket connected.")
            asyncio.create_task(self._keep_websocket_alive())
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Twelvedata WebSocket: {e}")
            self._ws_connection = None
            return False

    async def _keep_websocket_alive(self):
        """
        Keeps the WebSocket connection alive by sending heartbeats.
        """
        if self._ws_connection:
            try:
                while self._ws_connection.is_connected():
                    await self._ws_connection.keep_alive()
                    await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"WebSocket keep-alive error: {e}")
            finally:
                if self._ws_connection:
                    logging.info("WebSocket keep-alive routine ending.")

    async def stop_websocket(self):
        """
        Disconnects the Twelvedata WebSocket.
        """
        if self._ws_connection:
            logging.info("Disconnecting Twelvedata WebSocket...")
            await self._ws_connection.disconnect()
            self._ws_connection = None
            logging.info("Twelvedata WebSocket disconnected.")