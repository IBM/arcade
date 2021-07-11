# Copyright 2020 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import io
import os
from typing import List, IO, Optional, Protocol
import ibm_boto3  # type: ignore
from ibm_botocore.client import Config  # type: ignore
from ibm_boto3.resources.base import ServiceResource  # type: ignore


def build_cos_client() -> ServiceResource:
    '''Uses environment variables to build a COS client.'''
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
    '''The protocol that COS buckets need to implement.'''
    def list_file_names(self) -> List[str]:
        '''Lists all the file names in the bucket.'''
        ...

    def download_fileobj(self, file_name: str) -> Optional[IO[bytes]]:
        '''Downloads the contents of the given object in the bucket.'''
        ...


class IBMBucket:
    '''A bucket abstraction around IBM's cloud object storage.'''
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


class FileSystemBucket:
    '''A bucket that uses local file system data.'''

    def __init__(self, bucket_name: str,
                 data_path: str = '/arcade/tests/test_data/oem') -> None:
        self.name = bucket_name
        self.data_path = data_path

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
