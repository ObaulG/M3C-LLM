import requests


def check_api_key_usage(api_key):
    url = "https://api.mistral.ai/v1/usage"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        usage_data = response.json()
        print("API Key Usage Details:")
        print(usage_data)
    else:
        print(f"Failed to fetch usage details. Status code: {response.status_code}")
        print(response.text)
