import requests

url = "https://apidadosabertos.saude.gov.br/v1/arboviroses/dengue"

headers = {
    "accept": "application/json"
}

params = {
    "page": 1,
    "size": 10
}

response = requests.get(url, headers=headers, params=params)

print("Status:", response.status_code)
print(response.text[:1000])