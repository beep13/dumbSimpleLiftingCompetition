import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    S3_BUCKET = os.environ.get("S3_BUCKET")
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')  # Default to us-east-1 if not set
    S3_LOCATION = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/" if S3_BUCKET else None
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True
    UPLOAD_FOLDER = "static/profile_pictures"

class ProductionConfig(Config):
    DEBUG = False
    # Add any production-specific configurations here

class TestingConfig(Config):
    TESTING = True
    # Add any testing-specific configurations here

# You can add more environment-specific configs as needed
