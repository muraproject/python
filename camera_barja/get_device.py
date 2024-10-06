import requests
from requests.auth import HTTPDigestAuth

url = "http://8.215.44.249:3466/LAPI/V1.0/Channels/100/Smart/CrossLineDetection/Areas"
auth = HTTPDigestAuth('admin', 'admin!123')

response = requests.get(url, auth=auth)
print(response.json())