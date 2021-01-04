import io
import os
from typing import List, IO, Optional, Protocol
import ibm_boto3  # type: ignore
from ibm_botocore.client import Config  # type: ignore
from ibm_boto3.resources.base import ServiceResource  # type: ignore


def build_cos_client() -> ServiceResource:
    cos_endpoint = os.environ.get('COS_ENDPOINT')
    cos_api_key_id = os.environ.get('COS_API_KEY_ID')
    cos_instance_crn = os.environ.get('COS_INSTANCE_CRN')
    cos_client = ibm_boto3.resource('s3',
                                    ibm_api_key_id=cos_api_key_id,
                                    ibm_service_instance_id=cos_instance_crn,
                                    config=Config(signature_version='oauth'),
                                    endpoint_url=cos_endpoint)
    return cos_client


class COSBucket(Protocol):
    def list_file_names(self) -> List[str]:
        ...

    def download_fileobj(self, file_name: str) -> Optional[IO[bytes]]:
        ...


class Bucket():
    def __init__(self, cos_client: ServiceResource, bucket_name: str):
        self.cos_client = cos_client
        self.name = bucket_name

    def list_file_names(self) -> List[str]:
        try:
            bucket = self.cos_client.Bucket(self.name)
            files = bucket.objects.all()
            file_names = [f.key for f in files]
            return file_names
        except Exception:
            return []

    def download_fileobj(self, file_name: str) -> Optional[IO[bytes]]:
        try:
            cos_object = self.cos_client.Object(self.name, file_name).get()
            obj_bytes = cos_object['Body'].read()
            file_obj = io.BytesIO(obj_bytes)
            return file_obj
        except Exception:
            return None


class TestBucket:
    data_path = '/arcade/tests/test_data/oem'

    def list_file_names(self) -> List[str]:
        try:
            return os.listdir(self.data_path)
        except Exception:
            return []

    def download_fileobj(self, file_name: str) -> Optional[IO[bytes]]:
        file_path = f'{self.data_path}/{file_name}'
        try:
            with open(file_path, 'rb') as f:
                obj_bytes = f.read()
                file_obj = io.BytesIO(obj_bytes)
                return file_obj
        except Exception:
            return None
