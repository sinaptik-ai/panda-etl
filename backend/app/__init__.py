from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__, static_folder='../tmp')
    app.config.from_object('app.config.Config')

    CORS(app, resources={r"/*": {"origins": "*"}})

    db.init_app(app)
    migrate.init_app(app, db)

    @app.route('/assets/<path:filename>')
    def custom_static(filename):
        return send_from_directory(app.static_folder, filename)

    with app.app_context():
        from . import models
        from .routes import register_routes
        register_routes(app)
        db.create_all()

    return app
