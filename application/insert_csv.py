import pandas as pd
import mysql.connector
import os

def insert_csv_to_mysql(csv_path):
    df = pd.read_csv(csv_path)

    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT'))
    )
    cursor = conn.cursor()

    for _, row in df.iterrows():
        apply_link = row.get('Apply Link', 'Not Available')
        if len(apply_link) > 1024:
            apply_link = apply_link[:1024]

        cursor.execute("""
    INSERT INTO jobs (title, company, location, apply_link)
    VALUES (%s, %s, %s, %s)""",
    (
    row.get('Title', 'Unknown'),
    row.get('Company', 'Unknown'),
    row.get('Location', 'Unknown'),
    row.get('Apply Link', 'Not Available')[:1024]
    ))

        print(f"Inserted: {row.get('Title', 'Unknown')} at {row.get('Company', 'Unknown')}")

    conn.commit()
    cursor.close()
    conn.close()
