import boto3
from botocore.exceptions import ClientError, ParamValidationError
from flask import current_app
import logging
from werkzeug.utils import secure_filename
from botocore.config import Config
from PIL import Image
import io

logging.basicConfig(level=logging.DEBUG)

def get_s3_client():
    return boto3.client('s3', config=Config(s3={'addressing_style': 'path'}))

def upload_file_to_s3(file, user_id):
    from app import db, User
    
    if file:
        s3_client = get_s3_client()
        bucket_name = current_app.config['S3_BUCKET']
        
        # Resize image
        img = Image.open(file)
        img.thumbnail((500, 375))  # Resize to max 500x375 while maintaining aspect ratio
        
        # Save to in-memory file
        in_mem_file = io.BytesIO()
        img.save(in_mem_file, format=img.format)
        in_mem_file.seek(0)
        
        # Generate a unique filename
        file_name = f"profile_pictures/{user_id}/{secure_filename(file.filename)}"
        
        try:
            # Upload resized image
            s3_client.upload_fileobj(
                in_mem_file,
                bucket_name,
                file_name,
                ExtraArgs={'ACL': 'public-read'}
            )
            file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
            
            current_app.logger.info(f"Uploaded file URL: {file_url}")
        except ClientError as e:
            current_app.logger.error(f"Error uploading file: {str(e)}")
            return None
    else:
        # Use placeholder avatar if no file is provided
        file_url = 'placeholderAvatar.jpg'

    user = User.query.get(user_id)
    if user:
        user.profile_picture = file_url
        db.session.commit()
    return file_url

def delete_file_from_s3(filename):
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=current_app.config["S3_BUCKET"], Key=filename)
    except ClientError as e:
        print("Something Happened: ", e)
        return False
    return True
