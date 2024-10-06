import requests
from requests.auth import HTTPDigestAuth

base_url = "http://8.215.44.249:3466/LAPI/V1.0"
auth = HTTPDigestAuth('admin', 'admin!123')

# Periksa kemampuan perangkat
def check_capabilities():
    url = f"{base_url}/Channels/0/Smart/Capabilities"
    response = requests.get(url, auth=auth)
    return response.json()

capabilities = check_capabilities()
print("Kemampuan perangkat:", capabilities)