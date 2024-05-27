import requests
import redis
import os
import json
import pandas as pd

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
    cleaned_data = [{k: v for k, v in item.items() if v is not None} for item in data]
    df = pd.json_normalize(cleaned_data)
    df = df[df['actived'] == True]
    df.drop(['actived', 'shelterSupplies', 'pix', 'street', 'neighbourhood', 'streetNumber', 'prioritySum', 'zipCode', 'createdAt'], axis=1, inplace=True)
    
    return df

def main():
    try:
        shelters = fetch_shelter_data()
        id_count = sum(1 for item in shelters if "id" in item)
        print(f"Shelters: {id_count}")

        cleaned_shelters_df = clean_data(shelters)
        # Convert the DataFrame to a JSON string
        cleaned_shelters_json = cleaned_shelters_df.to_json(orient='records')

        # Store the cleaned shelter data in Redis
        client.set('shelters', cleaned_shelters_json)
        print('Shelter data has been updated in Redis')

        if os.getenv('FLASK_ENV') != 'production':
            # Save the cleaned shelter data to a JSON file
            with open('test.json', 'w') as f:
                json.dump(json.loads(cleaned_shelters_json), f, indent=4)
            print('Shelter data has been saved to test.json')
    except Exception as err:
        print(f'Error fetching shelter data: {err}')

if __name__ == "__main__":
    main()
