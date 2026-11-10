import urllib.request
import json
import time

# Cache exchange rates for 12 hours
_RATES_CACHE = {
    "timestamp": 0,
    "rates": {
        "USD": 1.0,
        "ZAR": 18.25,
        "EUR": 0.92,
        "GBP": 0.79,
        "AED": 3.67,
        "AUD": 1.52,
        "CAD": 1.38,
        "CNY": 7.24,
        "JPY": 154.50
    }
}

CURRENCY_SYMBOLS = {
    "Document Default": "",
    "ZAR": "R",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AED": "AED ",
    "AUD": "A$",
    "CAD": "C$",
    "CNY": "¥",
    "JPY": "¥"
}


def get_live_rates() -> dict:
    """
    Fetches real-time daily spot exchange rates relative to USD.
    Falls back to cached / standard rates if network is unavailable.
    """
    now = time.time()
    # Cache valid for 12 hours
    if now - _RATES_CACHE["timestamp"] < 43200 and _RATES_CACHE["timestamp"] > 0:
        return _RATES_CACHE["rates"]

    try:
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=3.5) as response:
            data = json.loads(response.read().decode())
            if data and data.get("result") == "success" and "rates" in data:
                rates = data["rates"]
                for c in ["USD", "ZAR", "EUR", "GBP", "AED", "AUD", "CAD", "CNY", "JPY"]:
                    if c in rates:
                        _RATES_CACHE["rates"][c] = float(rates[c])
                _RATES_CACHE["timestamp"] = now
    except Exception:
        pass

    return _RATES_CACHE["rates"]


def get_exchange_rate(from_curr: str, to_curr: str) -> float:
    """Calculates cross-currency spot rate from_curr -> to_curr."""
    rates = get_live_rates()
    from_usd = rates.get(from_curr.upper(), 1.0)
    to_usd = rates.get(to_curr.upper(), 1.0)
    if from_usd <= 0:
        return 1.0
    return to_usd / from_usd


def format_converted_price(amount: float, from_curr: str, to_curr: str) -> str:
    """Formats converted price with original in brackets for engineering transparency."""
    if to_curr == "Document Default" or from_curr.upper() == to_curr.upper():
        sym = CURRENCY_SYMBOLS.get(from_curr.upper(), from_curr)
        return f"{sym}{amount:,.2f}"

    rate = get_exchange_rate(from_curr, to_curr)
    converted = amount * rate
    to_sym = CURRENCY_SYMBOLS.get(to_curr.upper(), to_curr)
    from_sym = CURRENCY_SYMBOLS.get(from_curr.upper(), from_curr)

    return f"{to_sym}{converted:,.2f} [Orig: {from_sym}{amount:,.2f} @ {rate:.4f}]"
