import requests
import json

API_KEY = "c77ffefeac9f85a34905d58584b630f4"  # Use a chave nova após regenerar!

url = "https://v3.football.api-sports.io/players"

headers = {
    "x-apisports-key": API_KEY
}

params = {
    "league": 71,   # Série A brasileira
    "season": 2024,
    "page": 1
}

response = requests.get(url, headers=headers, params=params)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))