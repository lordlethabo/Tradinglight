# your_trading_dashboard/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging
from typing import List, Dict, Any
import pandas as pd 

# Import settings from config.py
from config import SYMBOL, INTERVAL, TWELVEDATA_API_KEY, OHLCV_HISTORY_SIZE
# Import our custom modules
from market_data import MarketDataStreamer
from indicators import calculate_technical_indicators
# from signals import generate_signals # This will be added in a future step

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost:3000",  # Common for React/Vue development servers
    "http://localhost:8080",  # Another common dev server port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "http://localhost:8000", # If frontend is served directly by FastAPI or for local testing
    # Add your deployed frontend URL here when you go live (e.g., "https://your-dashboard.com")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Instances ---
data_streamer = MarketDataStreamer(SYMBOL, INTERVAL, TWELVEDATA_API_KEY, OHLCV_HISTORY_SIZE)
connected_clients: List[WebSocket] = []
global_latest_data: Dict[str, Any] = {}

# --- FastAPI Lifecycle Events ---
@app.on_event("startup")
async def startup_event():
    """
    Actions to perform when the FastAPI application starts up.
    """
    logging.info("Starting up FastAPI application...")
    success = await data_streamer.fetch_initial_historical_data()
    if not success:
        logging.error("Failed to fetch initial historical data. Application might not function correctly.")

    await data_streamer.start_websocket()
    
    asyncio.create_task(data_processing_and_broadcasting_task())
    logging.info("FastAPI application startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Actions to perform when the FastAPI application shuts down.
    """
    logging.info("Shutting down FastAPI application...")
    await data_streamer.stop_websocket()
    logging.info("FastAPI application shut down.")

# --- Background Data Processing and Broadcasting Task ---
async def data_processing_and_broadcasting_task():
    """
    This background task periodically checks for new OHLCV bars,
    recalculates indicators, and broadcasts data to frontend clients.
    """
    last_processed_bar_timestamp = None 
    
    while True:
        current_ohlcv_history = data_streamer.ohlcv_history
        
        if current_ohlcv_history:
            latest_bar = current_ohlcv_history[-1]
            
            if latest_bar['timestamp'] != last_processed_bar_timestamp:
                logging.info(f"New OHLC bar detected: {latest_bar['timestamp']}. Recalculating indicators...")
                
                df_ohlcv = data_streamer.get_ohlcv_dataframe()
                df_with_indicators = calculate_technical_indicators(df_ohlcv.copy())
                
                if not df_with_indicators.empty:
                    latest_indicators_series = df_with_indicators.iloc[-1]
                    latest_indicators_dict = {
                        k: v for k, v in latest_indicators_series.items() if pd.notna(v)
                    }

                    # --- Prepare data payload for frontend ---
                    global global_latest_data
                    global_latest_data = {
                        "latest_price": data_streamer.current_price,
                        "latest_indicators": latest_indicators_dict,
                        "ohlcv_data": list(data_streamer.ohlcv_history)[-50:], # Send last 50 bars for charting
                        "timestamp": latest_bar['timestamp'],
                        # "signals": current_signals # Placeholder for next step
                    }

                    # --- Broadcast to all connected WebSocket clients ---
                    message_to_send = json.dumps(global_latest_data, default=str)
                    
                    for client in list(connected_clients):
                        try:
                            await client.send_text(message_to_send)
                        except RuntimeError as e:
                            logging.warning(f"Client disconnected during send: {e}. Removing client.")
                            connected_clients.remove(client)
                        except Exception as e:
                            logging.error(f"Error sending data to client: {e}. Removing client.")
                            connected_clients.remove(client)
                    
                    last_processed_bar_timestamp = latest_bar['timestamp']
                else:
                    logging.warning("DataFrame with indicators is empty after calculation, skipping broadcast.")
        
        await asyncio.sleep(0.5) # Check every 0.5 seconds

# --- FastAPI REST Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def get_root():
    return """
        <h1>Trading Dashboard Backend Running</h1>
        <p>Connect to the WebSocket at <code>ws://localhost:8000/ws</code> for real-time data.</p>
        <p>You can also get the latest processed data via REST at <code>/latest_data</code>.</p>
        <p>Check your console for real-time data and indicator updates!</p>
    """

@app.get("/latest_data")
async def get_latest_processed_data():
    return global_latest_data

# --- FastAPI WebSocket Endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logging.info(f"New WebSocket client connected from {websocket.client.host}:{websocket.client.port}. Total clients: {len(connected_clients)}")

    if global_latest_data:
        try:
            await websocket.send_text(json.dumps(global_latest_data, default=str))
        except Exception as e:
            logging.error(f"Error sending initial data to new client: {e}")

    try:
        while True:
            # This loop primarily keeps the connection open.
            # Client messages can be received here if needed, but not strictly for data streaming.
            await websocket.receive_text() 
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logging.info(f"WebSocket client disconnected. Total clients: {len(connected_clients)}")
    except Exception as e:
        logging.error(f"WebSocket error for client {websocket.client.host}:{websocket.client.port}: {e}. Removing client.")
        connected_clients.remove(websocket)