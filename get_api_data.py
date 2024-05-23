import requests
import redis
import os
import json

# Set the Redis URL
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
client = redis.Redis.from_url(redis_url)

def fetch_shelter_data():
    endpoint = "https://api.sos-rs.com/shelters?perPage=100"
    shelters = []
    total = 5000
    page = 1

    while len(shelters) != total:
        uri = f"{endpoint}&page={page}"
        response = requests.get(uri)
        data = response.json()
        results = data['data']['results']
        count = data['data']['count']

        shelters.extend(results)
        total = count
        page += 1

    return shelters

def main():
    try:
        shelters = fetch_shelter_data()
        # Store the shelter data in Redis
        client.set('shelters', json.dumps(shelters))
        print('Shelter data has been updated in Redis')
    except Exception as err:
        print(f'Error fetching shelter data: {err}')

if __name__ == "__main__":
    main()
