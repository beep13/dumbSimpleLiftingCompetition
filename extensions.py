from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    # Database configuration
    try:
        if os.getenv('FLASK_ENV') == 'production':
            database_url = os.getenv('DATABASE_URL')
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DEVELOPMENT_DATABASE_URL')

        if not app.config['SQLALCHEMY_DATABASE_URI']:
            raise ValueError("Database URL is not set")

        logger.info(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    except Exception as e:
        logger.error(f"Error configuring database: {str(e)}")
        raise

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)
