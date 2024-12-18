import requests

def send_post_request(kpj):
    url = "https://sipp.bpjsketenagakerjaan.go.id/tenaga-kerja/baru/get-tk-kpj"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        "Accept": "*/*",
        "Accept-Language": "id,en-US;q=0.7,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://sipp.bpjsketenagakerjaan.go.id",
        "Connection": "keep-alive",
        "Cookie": "_sipp=s%3AsHHaqX0wN_qKzs8ouyVA-eYaApikmsmx.QLS3rThpjJuBk8XUUmalHxt9lG0RtVPvMzTj8QCbcf0; BIGipServerSIPP_PUBLIK.app~SIPP_PUBLIK_pool=!zeYvCexs8qmHbS3KYN7OQ2yB5JWfykwiFTzjF5U0NrWSQskw8emeBGEPOO+IMsWnwdxnI2lbdFayyBetbE4fqRYlmlaRa+sgoSsIY7W0Xw==; TS01452ab3=011e8ab0a05ca7b5d3a5748b6ffeefa78d1fdf0ddb838761dc7d70c8d14c058c7a749c2293979204ae06da0b0207dfae27daeebefe; _ga_SV5ZXXMJ9X=GS1.1.1734498538.1.1.1734498981.0.0.0; _ga=GA1.3.1145381428.1734498539; _gid=GA1.3.1754285437.1734498539",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0",
    }
    data = {"kpj": kpj}
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        print(f"Response for KPJ {kpj}:\n{response.text}\n")
    except requests.exceptions.RequestException as e:
        print(f"Failed to process KPJ {kpj}: {e}")

def main():
    print("Enter KPJ numbers (one per line, empty line to finish):")
    kpj_list = []
    while True:
        kpj = input().strip()
        if not kpj:  # Break on empty input
            break
        kpj_list.append(kpj)

    print("\nProcessing KPJ numbers...\n")
    for kpj in kpj_list:
        send_post_request(kpj)

if __name__ == "__main__":
    main()
