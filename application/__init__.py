from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from . import pages
from . import jobs_bp
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(pages.bp)
    app.register_blueprint(jobs_bp.jobs_bp)
    return app
