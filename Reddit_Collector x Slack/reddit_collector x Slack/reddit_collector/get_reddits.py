import requests
from requests.auth import HTTPBasicAuth
import sys
from pprint import pprint
import os
from pymongo import MongoClient

sys.stdout.reconfigure(encoding='utf-8')

def connect_to_mongodb():
    """
    Connects to MongoDB and returns the database and collection objects.
    """
    mongo_client = MongoClient(os.getenv('MONGODB_URI'))
    db = mongo_client['reddit']
    collection = db['reedit_bot']
    return db, collection

def insert_post(collection, post):
    """
    Inserts a post into the MongoDB collection.
    """
    collection.insert_one(post)

def get_access_token():
    """
    Retrieves the access token from the Reddit API.
    """
    basic_auth = HTTPBasicAuth(
        username=os.getenv('client_id'),
        password=os.getenv('secret')
    )

    headers = {
        'User-Agent': 'PokemonBot/2.3'
    }

    grant_information = {
        'grant_type': 'password',
        'username': os.getenv('username'),  # REDDIT USERNAME
        'password': os.getenv('password')  # REDDIT PASSWORD
    }

    post_url = "https://www.reddit.com/api/v1/access_token"

    response = requests.post(
        url=post_url,
        headers=headers,
        data=grant_information,
        auth=basic_auth
    ).json()

    return response['access_token']

def download_pokemon_subreddit_titles(access_token):
    """
    Downloads the most popular Pokémon subreddit titles using the provided access token.
    """
    headers = {
        'User-Agent': 'PokemonBot/2.3',
        'Authorization': f'Bearer {access_token}'
    }

    topic = 'pokemon'
    url = f"https://oauth.reddit.com/r/{topic}/hot"

    response = requests.get(url=url, headers=headers).json()

    return response.get('data', {}).get('pokemon', [])

# Connect to MongoDB
db, collection = connect_to_mongodb()

# Retrieve access token
access_token = get_access_token()

# Download subreddit titles
subreddit_titles = download_pokemon_subreddit_titles(access_token)

# Insert titles into MongoDB
for post in subreddit_titles:
    _id = post['data']['id']
    title = post['data']['title']
    mongo_input = {"_id": _id, 'text': title}
    print("ID:", _id)
    print("Title:", title)

    insert_post(collection, mongo_input)

