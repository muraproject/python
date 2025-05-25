import requests
import json
from datetime import datetime

# API URL and parameters
url = "http://36.67.153.74:8800/api/json"
params = {
    "sid": "4491325c11b6478090fb71e7d6da86fb",
    "cmd": "data-lcu-light",
    "ctrl": "list",
    "version": "1",
    "lang": "en_US",
    "pid": "855b7708e2434eae9cffb330e8c96da2"
}

# Request headers from the complete HTTP request
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "text/plain;charset=UTF-8",
    "Host": "36.67.153.74:8800",
    "Origin": "http://36.67.153.74:8800",
    "Referer": "http://36.67.153.74:8800/web/map/panels/lamp.html",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
}

# Cookies
cookies = {
    "AXWEBSID": "4491325c11b6478090fb71e7d6da86fb",
    "userFlag": "4491325c11b6478090fb71e7d6da86fb",
    "language": "en_US"
}

# Request body
body_data = {
    "wheres": [
        {"k": "cuid", "o": "=", "v": "WMRTS6TCS8CJ"},
        {"k": "ctype", "o": "=", "v": 17},
        {"k": "luid", "o": "=", "v": "054024600180"}
    ],
    "orders": []
}

# Convert body to JSON string
body = json.dumps(body_data)

# Make the POST request
try:
    response = requests.post(
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        data=body,
        verify=False  # Note: This disables SSL verification which is not recommended for production
    )
    
    # Check if the request was successful
    if response.status_code == 200:
        # Print the raw response for debugging
        print("Raw Response:")
        print(response.text)
        print("\n" + "-"*50 + "\n")
        
        # Handle the specific "1||" prefix in the response
        if response.text.startswith("1||"):
            print("Detected '1||' prefix, removing it before parsing")
            json_text = response.text[3:]  # Remove the first 3 characters
            try:
                result = json.loads(json_text)
                
                # Print the parsed JSON response
                print("Parsed JSON Response:")
                print(json.dumps(result, indent=2))
                
                # Process timestamps if it's an array with items
                if isinstance(result, list) and len(result) > 0:
                    print("\nTimestamp Analysis:")
                    for row in result:
                        timestamp_fields = ["rtime", "ltime", "dtime", "qstime"]
                        for field in timestamp_fields:
                            if field in row and row[field]:
                                timestamp = row[field]
                                date_time = datetime.fromtimestamp(timestamp / 1000)  # Convert ms to seconds
                                print(f"{field}: {timestamp} = {date_time}")
                
                    # Extract specific fields of interest from the first item
                    row = result[0]
                    fields_of_interest = ["e", "pf", "life", "enabled"]
                    print("\nFields of Interest:")
                    for field in fields_of_interest:
                        if field in row:
                            print(f"{field}: {row[field]}")
            
            except json.JSONDecodeError as json_error:
                print(f"JSON parsing error after prefix removal: {json_error}")
                print("Response content after prefix removal:", json_text)
        else:
            print("Response doesn't start with expected '1||' prefix")
            try:
                # Try to parse anyway
                result = response.json()
                print("Parsed JSON Response:")
                print(json.dumps(result, indent=2))
            except json.JSONDecodeError as json_error:
                print(f"JSON parsing error: {json_error}")
    else:
        print(f"Request failed with status code: {response.status_code}")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"An error occurred: {e}")
    import traceback
    traceback.print_exc()