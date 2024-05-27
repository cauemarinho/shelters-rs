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

def clean_data(data):
    """Remove items with null values from the data."""
    return [{k: v for k, v in item.items() if v is not None} for item in data]

def main():
    try:
        shelters = fetch_shelter_data()
        id_count = sum(1 for item in shelters if "id" in item)
        print(f"Shelters: {id_count}")

        cleaned_shelters = clean_data(shelters)
        # Store the cleaned shelter data in Redis
        client.set('shelters', json.dumps(cleaned_shelters))
        print('Shelter data has been updated in Redis')

        if os.getenv('FLASK_ENV') != 'production':
            # Save the cleaned shelter data to a JSON file
            with open('test.json', 'w') as f:
                json.dump(cleaned_shelters, f, indent=4)
            print('Shelter data has been saved to test.json')
    except Exception as err:
        print(f'Error fetching shelter data: {err}')

if __name__ == "__main__":
    main()