# your_trading_dashboard/config.py

# Your Twelvedata API Key
TWELVEDATA_API_KEY = "eda1e0b1326840358fd7015023fbe7a0" # << REMEMBER TO REPLACE THIS WITH YOUR OWN KEY FOR PRODUCTION!

# Symbol and Interval for trading
SYMBOL = "EUR/GBP"
# Choose interval based on your binary options needs.
# "1min" is generally good for deriving signals for both 2-min and 5-min expiries.
INTERVAL = "1min"

# Number of historical data points (OHLC bars) to keep in memory for indicator calculation
# 200-300 bars should be sufficient for most common indicators.
OHLCV_HISTORY_SIZE = 300