import requests

BASE_URL = "http://localhost:8000/api"

def main():
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/login/", data={"username": "analyst", "password": "demo1234"})
    if resp.status_code != 200:
        print("Login failed:", resp.text)
        return
    token = resp.json()["token"]
    headers = {"Authorization": f"Token {token}"}

    print("Fetching data sources...")
    resp = requests.get(f"{BASE_URL}/sources/datasources/", headers=headers)
    sources = resp.json()
    if isinstance(sources, dict) and "results" in sources:
        sources = sources["results"]

    
    print("Sources:", sources)
    sap_source = next(s for s in sources if "SAP" in s.get("display_name", ""))
    utility_source = next(s for s in sources if "Electricity" in s.get("display_name", ""))
    travel_source = next(s for s in sources if "Travel" in s.get("display_name", ""))

    print("Uploading SAP...")
    with open("sample_data/sap_mb51_sample.csv", "rb") as f:
        resp = requests.post(f"{BASE_URL}/ingestion/upload/", headers=headers, data={"source_id": sap_source["id"]}, files={"file": f})
        print("SAP Response:", resp.status_code, resp.text)

    print("Uploading Utility...")
    with open("sample_data/utility_electricity_sample.csv", "rb") as f:
        resp = requests.post(f"{BASE_URL}/ingestion/upload/", headers=headers, data={"source_id": utility_source["id"]}, files={"file": f})
        print("Utility Response:", resp.status_code, resp.text)

    print("Uploading Travel...")
    with open("sample_data/travel_concur_sample.csv", "rb") as f:
        resp = requests.post(f"{BASE_URL}/ingestion/upload/", headers=headers, data={"source_id": travel_source["id"]}, files={"file": f})
        print("Travel Response:", resp.status_code, resp.text)

if __name__ == "__main__":
    main()
