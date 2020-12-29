import io
import os
import pytest
from arcade.data_access.cos.oem import COSOEMData


class TestBucket:
    data_path = 'tests/test_data/oem'

    def list_file_names(self):
        try:
            return os.listdir(self.data_path)
        except Exception:
            return []

    def download_fileobj(self, file_name):
        file_path = f'{self.data_path}/{file_name}'
        try:
            with open(file_path, 'rb') as f:
                obj_bytes = f.read()
                file_obj = io.BytesIO(obj_bytes)
                return file_obj
        except Exception:
            return None


@pytest.fixture
def oem_data():
    bucket = TestBucket()
    cos_oem = COSOEMData(bucket)
    return cos_oem


def test_latest_date(oem_data):
    assert oem_data.date == '20201124'


def test_set_date(oem_data):
    oem_data.get_oem_data_from_cos(date='20201121')
    iss_data = oem_data.get('25544')
    assert iss_data.creation_date.startswith('2020-11-21')


def test_load_oem_data(oem_data):
    oem_data.get_oem_data_from_cos()
    iss_data = oem_data.get('25544')
    assert iss_data.object_name == 'ISS (ZARYA)'


def test_handle_no_data(oem_data):
    oem_data.get_oem_data_from_cos(aso_ids=['12345'])
    assert not oem_data.get('12345')
