from flask import Blueprint, render_template
import mysql.connector
from config import Config
import os

bp = Blueprint('pages', __name__, template_folder='templates/pages')

@bp.route('/')
def home():
    return render_template('jobs.html')
