# your_trading_dashboard/indicators.py

import pandas as pd
import talib as ta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates various technical indicators and adds them as new columns to the DataFrame.
    """
    if df.empty or not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        logging.warning("DataFrame is empty or missing OHLC columns. Cannot calculate indicators.")
        return df

    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['open', 'high', 'low', 'close'])

    if df.empty:
        logging.warning("DataFrame is empty after cleaning. Cannot calculate indicators.")
        return df

    # --- 1. Relative Strength Index (RSI) ---
    df['RSI'] = ta.RSI(df['close'], timeperiod=14)

    # --- 2. Moving Averages ---
    df['SMA_20'] = ta.SMA(df['close'], timeperiod=20)
    df['SMA_50'] = ta.SMA(df['close'], timeperiod=50)

    df['EMA_20'] = ta.EMA(df['close'], timeperiod=20)
    df['EMA_50'] = ta.EMA(df['close'], timeperiod=50)

    # --- 3. Momentum (Rate of Change - ROC) ---
    df['MOMENTUM_ROC_10'] = ta.ROC(df['close'], timeperiod=10)

    # --- 4. Volatility (Average True Range - ATR) ---
    df['ATR'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    df = df.dropna()
    
    return df