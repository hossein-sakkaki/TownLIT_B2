# utils/common/ip.py

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



# اگر احتمال جعل IP یا حملات DOS بالا باشد، یا در CDN/proxyهای پیچیده باشید
# def get_client_ip(request, trusted_proxies=None):
#     """
#     Extract client IP while accounting for proxy chains.
#     Only trusts X-Forwarded-For if sent through a known proxy.
#     """
#     trusted_proxies = trusted_proxies or []

#     x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
#     remote_addr = request.META.get("REMOTE_ADDR", "")

#     if x_forwarded_for:
#         forwarded_ips = [ip.strip() for ip in x_forwarded_for.split(",")]
#         # Remove trusted proxies from the end (right to left)
#         while forwarded_ips and forwarded_ips[-1] in trusted_proxies:
#             forwarded_ips.pop()
#         ip = forwarded_ips[-1] if forwarded_ips else remote_addr
#     else:
#         ip = remote_addr

#     return ip
