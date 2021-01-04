import pytest
from arcade.data_access.cos import TestBucket
from arcade.data_access.cos.oem import COSOEMData


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
