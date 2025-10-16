from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from . import pages
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(pages.bp)
    return app
