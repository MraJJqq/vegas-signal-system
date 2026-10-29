"""Canonical V9 market universe shared by scanner and Bark notifier."""

CORE_MARKETS = ("BTC", "HYPE", "XAU", "CL")
STOCKS = (
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "INTC",
    "QCOM", "AMD", "TSM", "AVGO", "ORCL", "ARM", "MU", "ASML", "SNDK",
    "SKHYNIX", "MRVL", "GLW", "HOOD", "CBRS", "SPCX",
)

# Bitget scanner uses exchange symbols; notifier uses the same base symbols.
SYMBOLS = tuple(f"{symbol}USDT" for symbol in (*CORE_MARKETS, *STOCKS))
ALLOWED_SYMBOLS = frozenset((*CORE_MARKETS, *STOCKS))
