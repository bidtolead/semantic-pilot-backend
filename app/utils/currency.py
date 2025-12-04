"""Currency mapping for locations based on DataForSEO location codes."""

# Mapping of country ISO codes to currency codes
COUNTRY_TO_CURRENCY = {
    "US": "USD",
    "GB": "GBP",
    "CA": "CAD",
    "AU": "AUD",
    "NZ": "NZD",
    "IE": "EUR",
    "IN": "INR",
    "PH": "PHP",
    "SG": "SGD",
    "AE": "AED",
    "IL": "ILS",
    "ZA": "ZAR",
    "NG": "NGN",
    "MY": "MYR",
    "PK": "PKR",
    "KE": "KES",
    "GH": "GHS",
}

# Mapping of location codes to country ISO codes (subset of common locations)
LOCATION_CODE_TO_COUNTRY = {
    # US
    "1023191": "US",  # New York
    "1014044": "US",  # Los Angeles
    "1012728": "US",  # Chicago
    "1021224": "US",  # Houston
    "1023040": "US",  # Phoenix
    "1025197": "US",  # San Francisco
    "1026201": "US",  # Seattle
    "1013962": "US",  # Miami
    "2840": "US",     # United States
    # Canada
    "9000093": "CA",  # Toronto
    "9000071": "CA",  # Vancouver
    "9000040": "CA",  # Montreal
    "2124": "CA",     # Canada
    # UK
    "1006886": "GB",  # London
    "1006099": "GB",  # Manchester
    "2826": "GB",     # United Kingdom
    # Australia
    "1000339": "AU",  # Sydney
    "1000318": "AU",  # Melbourne
    "1000310": "AU",  # Brisbane
    "2036": "AU",     # Australia
    # New Zealand
    "1011036": "NZ",  # Auckland
    "1001460": "NZ",  # Wellington
    "2554": "NZ",     # New Zealand
    # Ireland
    "1015270": "IE",  # Dublin
    "2963": "IE",     # Ireland
    # India
    "1015269": "IN",  # Mumbai
    "1015271": "IN",  # Delhi
    "2276": "IN",     # India
    # Philippines
    "1030081": "PH",  # Manila
    "1651": "PH",     # Philippines
    # Singapore
    "1037199": "SG",  # Singapore
    "2702": "SG",     # Singapore
    # UAE
    "1015277": "AE",  # Dubai
    "1015278": "AE",  # Abu Dhabi
    "2784": "AE",     # United Arab Emirates
    # Israel
    "1023219": "IL",  # Tel Aviv
    "1023220": "IL",  # Jerusalem
    "2376": "IL",     # Israel
    # South Africa
    "1028329": "ZA",  # Johannesburg
    "1028330": "ZA",  # Cape Town
    "2710": "ZA",     # South Africa
    # Nigeria
    "1032258": "NG",  # Lagos
    "1615": "NG",     # Nigeria
    # Malaysia
    "1026184": "MY",  # Kuala Lumpur
    "1681": "MY",     # Malaysia
    # Pakistan
    "1027481": "PK",  # Karachi
    "1027482": "PK",  # Lahore
    "1682": "PK",     # Pakistan
    # Kenya
    "1025009": "KE",  # Nairobi
    "1232": "KE",     # Kenya
    # Ghana
    "1024019": "GH",  # Accra
    "2288": "GH",     # Ghana
}

def get_currency_for_location(location_code: str) -> str:
    """Get currency code for a location.
    
    Args:
        location_code: DataForSEO location code (e.g., "1011036" for Auckland)
    
    Returns:
        Currency code (e.g., "NZD"), or "USD" as fallback
    """
    country_code = LOCATION_CODE_TO_COUNTRY.get(str(location_code))
    if country_code:
        return COUNTRY_TO_CURRENCY.get(country_code, "USD")
    return "USD"

def format_bid(bid_micros: int, currency: str) -> str:
    """Format bid in micros to readable currency format.
    
    Args:
        bid_micros: Bid amount in micros (e.g., 670000 = $0.67)
        currency: Currency code (e.g., "USD")
    
    Returns:
        Formatted string (e.g., "$0.67 USD" or "₹50.34 INR")
    """
    if bid_micros is None:
        return "-"
    
    bid_amount = bid_micros / 1_000_000
    
    currency_symbols = {
        "USD": "$",
        "GBP": "£",
        "EUR": "€",
        "CAD": "C$",
        "AUD": "A$",
        "NZD": "NZ$",
        "INR": "₹",
        "PHP": "₱",
        "SGD": "S$",
        "AED": "AED",
        "ILS": "₪",
        "ZAR": "R",
        "NGN": "₦",
        "MYR": "RM",
        "PKR": "₨",
        "KES": "KSh",
        "GHS": "GH₵",
    }
    
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{bid_amount:.2f} {currency}"
