"""Indian PIN code to GST 2-digit state code mapping registry."""

import re
from razoragentMesh.packages.mandateEngine.settlementExceptions import (
    InvalidPincodeException,
)

pincodePattern: str = r"^[1-9][0-9]{5}$"

# First 2 digits of Indian PIN mapped to GST State Code
pinPrefixToStateCode: dict[str, str] = {
    "11": "07",  # Delhi
    "12": "06",  # Haryana
    "13": "06",  # Haryana
    "14": "03",  # Punjab
    "15": "03",  # Punjab
    "16": "04",  # Chandigarh
    "17": "02",  # Himachal Pradesh
    "18": "01",  # Jammu & Kashmir
    "19": "01",  # Jammu & Kashmir
    "20": "09",  # Uttar Pradesh
    "21": "09",  # Uttar Pradesh
    "22": "09",  # Uttar Pradesh
    "23": "09",  # Uttar Pradesh
    "24": "09",  # Uttar Pradesh
    "25": "09",  # Uttar Pradesh
    "26": "09",  # Uttar Pradesh
    "27": "09",  # Uttar Pradesh
    "28": "09",  # Uttar Pradesh
    "30": "08",  # Rajasthan
    "31": "08",  # Rajasthan
    "32": "08",  # Rajasthan
    "33": "08",  # Rajasthan
    "34": "08",  # Rajasthan
    "36": "24",  # Gujarat
    "37": "24",  # Gujarat
    "38": "24",  # Gujarat
    "39": "24",  # Gujarat
    "40": "27",  # Maharashtra
    "41": "27",  # Maharashtra
    "42": "27",  # Maharashtra
    "43": "27",  # Maharashtra
    "44": "27",  # Maharashtra
    "45": "23",  # Madhya Pradesh
    "46": "23",  # Madhya Pradesh
    "47": "23",  # Madhya Pradesh
    "48": "23",  # Madhya Pradesh
    "49": "22",  # Chhattisgarh
    "50": "36",  # Telangana
    "51": "37",  # Andhra Pradesh
    "52": "37",  # Andhra Pradesh
    "53": "37",  # Andhra Pradesh
    "56": "29",  # Karnataka
    "57": "29",  # Karnataka
    "58": "29",  # Karnataka
    "59": "29",  # Karnataka
    "60": "33",  # Tamil Nadu
    "61": "33",  # Tamil Nadu
    "62": "33",  # Tamil Nadu
    "63": "33",  # Tamil Nadu
    "64": "33",  # Tamil Nadu
    "67": "32",  # Kerala
    "68": "32",  # Kerala
    "69": "32",  # Kerala
    "70": "19",  # West Bengal
    "71": "19",  # West Bengal
    "72": "19",  # West Bengal
    "73": "19",  # West Bengal
    "74": "19",  # West Bengal
    "75": "21",  # Odisha
    "76": "21",  # Odisha
    "77": "21",  # Odisha
    "78": "18",  # Assam
    "79": "12",  # Arunachal Pradesh / NE states
    "80": "10",  # Bihar
    "81": "10",  # Bihar
    "82": "20",  # Jharkhand
    "83": "20",  # Jharkhand
    "84": "10",  # Bihar
    "85": "10",  # Bihar
}


def deriveStateCodeFromPincode(pincode: str) -> str:
    """Derives 2-digit GST state code from 6-digit Indian PIN code."""
    if not isinstance(pincode, str) or not re.match(pincodePattern, pincode):
        raise InvalidPincodeException(f"Invalid PIN code format: '{pincode}'")

    prefix = pincode[:2]
    if prefix not in pinPrefixToStateCode:
        raise InvalidPincodeException(f"Unmapped PIN prefix: '{prefix}'")

    return pinPrefixToStateCode[prefix]
