# utils/common/ip.py
import requests
from django.conf import settings


def get_client_ip(request):
    """
    Extract the client's IP address from the request.
    Gives priority to X-Forwarded-For if behind a proxy.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip



def get_location_from_ip(ip_address):
    """
    Return approximate location (city, region, country) based on IP address.
    """
    try:
        token = settings.IPINFO_API_KEY
        url = f"https://ipinfo.io/{ip_address}/json?token={token}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "city": data.get("city"),
                "region": data.get("region"),
                "country": data.get("country"),
                "timezone": data.get("timezone"),
                "org": data.get("org"),
                "latitude": float(data.get("loc", "0,0").split(",")[0]),
                "longitude": float(data.get("loc", "0,0").split(",")[1]),
                "postal": data.get("postal"),
            }

    except Exception:
        pass
    return {"city": None, "region": None, "country": None}