import requests
import json
import csv
import re

# Function to parse the curl input into JSON format
def parse_curl_to_json(curl_data):
    """Parses curl data to extract JSON-compatible URL, headers, and payload."""
    headers = {}
    url = ""
    data_section = None

    # Regex for parsing
    url_match = re.search(r'curl \"(.*?)\"', curl_data)
    if not url_match:
        url_match = re.search(r'curl "(.*?)"', curl_data)  # Adjust for Windows curl
    if url_match:
        url = url_match.group(1)

    header_matches = re.findall(r'-H \"(.*?)\"', curl_data)
    if not header_matches:
        header_matches = re.findall(r'-H "(.*?)"', curl_data)  # Adjust for Windows curl

    for header in header_matches:
        key, value = header.split(": ", 1)
        headers[key] = value

    data_match = re.search(r"--data-raw '(.*?)'", curl_data)
    if not data_match:
        data_match = re.search(r"--data-raw \"(.*?)\"", curl_data)  # Adjust for Windows curl
    if data_match:
        data_section = data_match.group(1)

    if not url or not headers or data_section is None:
        raise ValueError("Curl data is invalid. Ensure URL, headers, and payload are provided.")

    return url, headers, data_section

# Function to execute the request and save to CSV
def execute_and_save_to_csv(url, headers, payload, csv_filename, kpj_numbers):
    results = []

    for kpj in kpj_numbers:
        data = payload.replace("kpj=", f"kpj={kpj}")
        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            results.append({"KPJ": kpj, "Response": response.json()})
        else:
            results.append({"KPJ": kpj, "Response": f"Error {response.status_code}"})

    with open(csv_filename, mode='w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["KPJ", "Response"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow({"KPJ": result["KPJ"], "Response": json.dumps(result["Response"])})

    print(f"Data successfully saved to {csv_filename}")

# Main program
def main():
    current_curl_data = ""
    while True:
        print("\nChoose an option:")
        print("1. Update curl data/cookie")
        print("2. Enter KPJ data and execute")
        print("3. Exit")
        choice = input("Enter your choice (1/2/3): ")

        if choice == "1":
            current_curl_data = input("Enter curl data: ").strip()
            try:
                url, headers, payload = parse_curl_to_json(current_curl_data)
                print("Curl data updated successfully!")
            except ValueError as e:
                print(f"Error: {e}")
                current_curl_data = ""
        elif choice == "2":
            if not current_curl_data:
                print("Curl data has not been entered. Choose option 1 first.")
                continue

            kpj_input = input("Enter a list of KPJ numbers, separated by commas: ")
            kpj_numbers = [kpj.strip() for kpj in kpj_input.split(",")]

            csv_filename = input("Enter the name of the CSV file to save results (e.g., results.csv): ")
            try:
                execute_and_save_to_csv(url, headers, payload, csv_filename, kpj_numbers)
            except Exception as e:
                print(f"Execution error: {e}")
        elif choice == "3":
            print("Program exited.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
