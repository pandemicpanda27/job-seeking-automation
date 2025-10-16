import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='password',
    database='job_board'
)

print("connnted to MYSQL")
conn.close()
