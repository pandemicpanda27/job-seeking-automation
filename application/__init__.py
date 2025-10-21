from flask import Flask
from . import pages
from . import api_bp
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(pages.bp)
    app.register_blueprint(api_bp.api_bp)
    return app
