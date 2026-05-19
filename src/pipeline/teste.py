import requests

url = "https://v3.football.api-sports.io/players"
headers = {"x-apisports-key": "c77ffefeac9f85a34905d58584b630f4"}

for league_id in [72, 75, 76]:
    params = {"league": league_id, "season": 2024, "page": 1}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    print(f"Liga {league_id}: {data['paging']}")