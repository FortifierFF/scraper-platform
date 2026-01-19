"""
Image storage backends for saving scraped images.
Supports local filesystem and S3-compatible cloud storage.
"""
import os
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse
import requests
from typing import Optional


class ImageStorage(ABC):
    """Abstract base class for image storage backends."""
    
    @abstractmethod
    def save_image(self, image_url: str, dataset_id: str, content: bytes, extension: str) -> Optional[str]:
        """
        Save image and return the storage path/URL.
        
        Args:
            image_url: Original image URL
            dataset_id: Dataset ID for organization
            content: Image binary content
            extension: File extension (e.g., '.jpg')
        
        Returns:
            Storage path/URL or None if failed
        """
        pass
    
    @abstractmethod
    def image_exists(self, image_url: str, dataset_id: str, extension: str) -> bool:
        """Check if image already exists in storage."""
        pass


class LocalImageStorage(ImageStorage):
    """Local filesystem storage for images."""
    
    def __init__(self, base_path: str = '/app/data/images'):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_filepath(self, image_url: str, dataset_id: str, extension: str) -> Path:
        """Generate filepath for image."""
        url_hash = hashlib.sha256(image_url.encode()).hexdigest()
        filename = f"{url_hash}{extension}"
        dataset_dir = self.base_path / str(dataset_id)
        dataset_dir.mkdir(parents=True, exist_ok=True)
        return dataset_dir / filename
    
    def image_exists(self, image_url: str, dataset_id: str, extension: str) -> bool:
        """Check if image file exists."""
        filepath = self._get_filepath(image_url, dataset_id, extension)
        return filepath.exists()
    
    def save_image(self, image_url: str, dataset_id: str, content: bytes, extension: str) -> Optional[str]:
        """Save image to local filesystem."""
        filepath = self._get_filepath(image_url, dataset_id, extension)
        
        # Skip if already exists
        if filepath.exists():
            return f"images/{dataset_id}/{filepath.name}"
        
        # Save file
        try:
            with open(filepath, 'wb') as f:
                f.write(content)
            # Return relative path
            return f"images/{dataset_id}/{filepath.name}"
        except Exception as e:
            print(f'LocalImageStorage: Failed to save image: {e}')
            return None


class S3ImageStorage(ImageStorage):
    """S3-compatible cloud storage (AWS S3, DigitalOcean Spaces, etc.)."""
    
    def __init__(self, 
                 endpoint_url: str,
                 bucket_name: str,
                 access_key_id: str,
                 secret_access_key: str,
                 region: str = 'us-east-1'):
        try:
            import boto3
        except ImportError:
            raise ImportError('boto3 is required for S3 storage. Install with: pip install boto3')
        
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region
        )
    
    def _get_s3_key(self, image_url: str, dataset_id: str, extension: str) -> str:
        """Generate S3 key for image."""
        url_hash = hashlib.sha256(image_url.encode()).hexdigest()
        filename = f"{url_hash}{extension}"
        return f"images/{dataset_id}/{filename}"
    
    def image_exists(self, image_url: str, dataset_id: str, extension: str) -> bool:
        """Check if object exists in S3."""
        s3_key = self._get_s3_key(image_url, dataset_id, extension)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except self.s3_client.exceptions.ClientError:
            return False
    
    def save_image(self, image_url: str, dataset_id: str, content: bytes, extension: str) -> Optional[str]:
        """Upload image to S3."""
        s3_key = self._get_s3_key(image_url, dataset_id, extension)
        
        # Skip if already exists (return existing key)
        if self.image_exists(image_url, dataset_id, extension):
            return s3_key
        
        try:
            # Determine content type
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_type_map.get(extension.lower(), 'image/jpeg')
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType=content_type,
                ACL='public-read'  # Make images publicly accessible
            )
            # Return S3 key (you can construct full URL if needed)
            return s3_key
        except Exception as e:
            print(f'S3ImageStorage: Failed to upload image: {e}')
            return None


def get_image_storage():
    """
    Factory function to get the appropriate image storage backend.
    Reads from environment variables:
    - IMAGE_STORAGE_TYPE: 'local' or 's3' (default: 'local')
    - For S3: IMAGE_STORAGE_S3_ENDPOINT, IMAGE_STORAGE_S3_BUCKET, etc.
    """
    storage_type = os.environ.get('IMAGE_STORAGE_TYPE', 'local').lower()
    
    if storage_type == 's3':
        endpoint = os.environ.get('IMAGE_STORAGE_S3_ENDPOINT')
        bucket = os.environ.get('IMAGE_STORAGE_S3_BUCKET')
        access_key = os.environ.get('IMAGE_STORAGE_S3_ACCESS_KEY')
        secret_key = os.environ.get('IMAGE_STORAGE_S3_SECRET_KEY')
        region = os.environ.get('IMAGE_STORAGE_S3_REGION', 'us-east-1')
        
        if not all([endpoint, bucket, access_key, secret_key]):
            raise ValueError(
                'S3 storage requires: IMAGE_STORAGE_S3_ENDPOINT, '
                'IMAGE_STORAGE_S3_BUCKET, IMAGE_STORAGE_S3_ACCESS_KEY, '
                'IMAGE_STORAGE_S3_SECRET_KEY'
            )
        
        return S3ImageStorage(endpoint, bucket, access_key, secret_key, region)
    
    else:  # default to local
        base_path = os.environ.get('IMAGE_STORAGE_LOCAL_PATH', '/app/data/images')
        return LocalImageStorage(base_path)
