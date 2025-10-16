from flask import Blueprint, render_template
import mysql.connector
from config import Config
import os

bp = Blueprint('pages', __name__, template_folder='templates/pages')

@bp.route('/')
def home():
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=os.getenv('DB_PORT')
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('jobs.html', jobs=jobs)
