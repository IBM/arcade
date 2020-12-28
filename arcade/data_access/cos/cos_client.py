import os
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
