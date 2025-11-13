# trading_dashboard/main.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import logging
import json
from typing import List, Dict, Any
import pandas as pd

from config import SYMBOL, INTERVAL, TWELVEDATA_API_KEY, OHLCV_HISTORY_SIZE
from market_data import MarketDataStreamer
from indicators import calculate_technical_indicators
# Placeholder for future AI model integration
# from ai_model import generate_predictions  

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI(title="Tradinglight AI-Ready Backend")

# --- CORS configuration ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Add deployed frontend URL here
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Global instances ---
data_streamer = MarketDataStreamer(SYMBOL, INTERVAL, TWELVEDATA_API_KEY, OHLCV_HISTORY_SIZE)
connected_clients: List[WebSocket] = []
global_latest_data: Dict[str, Any] = {}

# --- Startup / Shutdown events ---
@app.on_event("startup")
async def startup_event():
    logging.info("Starting backend...")
    success = await data_streamer.fetch_initial_historical_data()
    if not success:
        logging.error("Failed to fetch initial historical data.")

    await data_streamer.start_websocket()
    asyncio.create_task(data_processing_loop())
    logging.info("Backend started.")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Shutting down backend...")
    await data_streamer.stop_websocket()
    logging.info("Backend shut down.")

# --- Background data processing ---
async def data_processing_loop():
    last_timestamp = None
    while True:
        ohlcv = data_streamer.ohlcv_history
        if ohlcv:
            latest_bar = ohlcv[-1]
            if latest_bar['timestamp'] != last_timestamp:
                df = data_streamer.get_ohlcv_dataframe()
                df_with_indicators = calculate_technical_indicators(df.copy())

                # --- ML Hook: placeholder for predictions ---
                # predictions = generate_predictions(df_with_indicators)

                if not df_with_indicators.empty:
                    latest_data = df_with_indicators.iloc[-1].dropna().to_dict()
                    global global_latest_data
                    global_latest_data = {
                        "latest_price": data_streamer.current_price,
                        "indicators": latest_data,
                        # "predictions": predictions,  # Will integrate ML later
                        "ohlcv": list(ohlcv)[-50:],
                        "timestamp": latest_bar['timestamp']
                    }

                    message = json.dumps(global_latest_data, default=str)
                    for client in list(connected_clients):
                        try:
                            await client.send_text(message)
                        except:
                            connected_clients.remove(client)

                last_timestamp = latest_bar['timestamp']
        await asyncio.sleep(0.5)

# --- REST endpoints ---
@app.get("/")
async def root():
    return {"message": "Tradinglight AI-Ready Backend running!"}

@app.get("/latest_data")
async def get_latest():
    return JSONResponse(content=global_latest_data)

# --- WebSocket endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logging.info(f"Client connected: {len(connected_clients)} total")

    if global_latest_data:
        await websocket.send_text(json.dumps(global_latest_data, default=str))

    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logging.info(f"Client disconnected: {len(connected_clients)} total")
