import time
import requests
import sqlalchemy
import pandas as pd

# Wait for 20 seconds for slackbot post
time.sleep(20)

# Slack webhook URL
WEBHOOK_URL = 'https://hooks.slack.com/services/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'

# Connecting to PostgreSQL
postgres_engine = sqlalchemy.create_engine('postgresql://miguelpinheiro:1234@postgresdb:5432/reedit_bot', echo=True)
connection = postgres_engine.connect()

# Querying data from PostgreSQL
query = 'SELECT * FROM post_sentiment LIMIT 5;'
df_post_sentiments = pd.read_sql(query, connection)

# Posting the data on Slack in batches
batch_size = 2  # Adjust the batch size as per your requirements
num_rows = len(df_post_sentiments)

for i in range(0, num_rows, batch_size):
    batch_df = df_post_sentiments.iloc[i:i+batch_size]

    data = {
        "blocks": []
    }

    for _, row in batch_df.iterrows():
        text = str(row['post_text'])
        sentiment = str(row['sentiment_score'])
        block = {
            "type": "divider"
        }
        data["blocks"].append(block)

        block = {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": text
            }
        }
        data["blocks"].append(block)

        block = {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": sentiment
            }
        }
        data["blocks"].append(block)

    requests.post(url=WEBHOOK_URL, json=data)

    if i + batch_size < num_rows:
        time.sleep(60)  # Sleep between batches

connection.close()

