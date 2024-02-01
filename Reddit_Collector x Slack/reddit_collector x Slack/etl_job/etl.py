import re
import logging
import time
import sqlalchemy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.WARNING)

# MongoDB connection
def mongodb_connection():
    """
    Connects to the MongoDB reddit database.
    """
    client = MongoClient(host="mongodb", port=27017)
    db = client.reddit
    return db

# Extract posts from MongoDB
def extract(db, number_of_posts):
    """
    Extracts posts from the MongoDB reddit database.
    """
    posts = db.reedit_bot
    extracted_posts = posts.find(limit=number_of_posts)
    return extracted_posts

# Clean post text using regular expressions
regex_list = [
    '@[A-Za-z0-9]+',   # To find @mentions
    '#',               # To find hashtag symbol
    'https?:\/\/\S+',  # To find most URLs
    "'"
]
def clean_post(post):
    """
    Cleans up the text of a post.
    """
    text = post['text']
    for regex in regex_list:
        text = re.sub(regex, '', text)
    return text

# Calculate sentiment score
analyzer = SentimentIntensityAnalyzer()
def sentiment_score(text):
    """
    Calculates the sentiment score of a text.
    """
    sentiment = analyzer.polarity_scores(text)
    score = sentiment['compound']
    return score

# Transform extracted post
def transform(post):
    """
    Transforms an extracted post by cleaning the text and calculating sentiment score.
    """
    text = clean_post(post)
    score = sentiment_score(text)
    return text, score

# PostgreSQL connection
def postgres_connection():
    """
    Establishes a connection to the PostgreSQL database.
    """
    pg_engine = sqlalchemy.create_engine(
        'postgresql://miguelpinheiro:1234@postgresdb:5432/reedit_bot',
        echo=True
    )
    connection = pg_engine.connect()
    return connection

# Load transformed data into PostgreSQL
def load(connection, transformed_data):
    """
    Loads post text and score into the PostgreSQL database.
    """
    create_table_query = sqlalchemy.text("""
    CREATE TABLE IF NOT EXISTS post_sentiment (
        post_text VARCHAR(500),
        sentiment_score NUMERIC
    );""")
    connection.execute(create_table_query)
    connection.commit()

    insert_query = sqlalchemy.text("""
    INSERT INTO post_sentiment VALUES (%s, %s);
    """)
    connection.execute(insert_query, transformed_data)
    connection.commit()

# ETL steps
def perform_etl():
    # MongoDB connection
    mongo_db = mongodb_connection()
    time.sleep(20)
    logging.warning('-----Posts already extracted from MongoDB-----')

    # Extract posts from MongoDB
    extracted_posts = extract(mongo_db, number_of_posts=10)

    # Transform data
    transformed_data = [transform(post) for post in extracted_posts]
    logging.warning('-----Transformed data already generated-----')

    # PostgreSQL connection
    pg_engine = postgres_connection()

    # Load data into PostgreSQL
    load(pg_engine, transformed_data)
    logging.warning('-----Data already loaded into PostgreSQL-----')

# Run the ETL process
perform_etl()
