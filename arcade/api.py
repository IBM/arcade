import os
import logging
from typing import List, Optional
from fastapi import FastAPI
import arcade.data_access.cos as cos
import arcade.models as models
from arcade.data_access.cos.oem import COSOEMData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_oem_data() -> COSOEMData:
    '''Builds the OEM dataset from data in cloud object storage.

    :return: The OEM data from COS
    '''
    oem_bucket: cos.COSBucket
    # Use local data in dev mode
    if os.environ.get('DEV'):
        oem_bucket = cos.TestBucket()
    else:
        cos_client = cos.build_cos_client()
        oem_bucket_name = os.environ.get('COS_BUCKET', '')
        oem_bucket = cos.Bucket(cos_client, oem_bucket_name)
    cos_oem_data = COSOEMData(oem_bucket)
    # Check to see if there is a file specifying the ASO IDs to fetch from
    # COS.  If no file exists then fetch all of the latest OEM data.
    aso_id_file = os.environ.get('OEM_ASO_ID_FILE')
    if aso_id_file:
        with open(aso_id_file) as id_file:
            print(aso_id_file)
            aso_ids = [line.strip() for line in id_file.readlines()]
    else:
        aso_ids = []
    cos_oem_data.get_oem_data_from_cos(aso_ids=aso_ids)
    return cos_oem_data


logger.info('Building OEM data set from COS...')
oem_dataset = build_oem_data()
logger.info('info data set finished.')

app = FastAPI(title='ARACADE')


def get_aso_from_oem(aso_id: str) -> Optional[models.ASO]:
    '''Builds an ASO model object from data in the OEM data set.

    :param aso_id: The ID of the ASO to build a model object for.

    :return: The ASO model object if the ASO is in the OEM dataset.
    '''
    oem_data = oem_dataset.get(aso_id)
    if oem_data is None:
        return None
    aso = models.ASO(aso_id=aso_id,
                     norad_id=aso_id,
                     cospar_id=oem_data.object_id,
                     aso_name=oem_data.object_name)
    return aso


@app.get('/asos')
async def get_asos() -> List[models.ASO]:
    '''Returns information on all the anthropogenic space objects (ASOs) that
    ARCADE knows about.
    '''
    aso_ids = oem_dataset.oem_data.keys()
    asos = []
    for aso_id in aso_ids:
        aso = get_aso_from_oem(aso_id)
        if not aso:
            continue
        asos.append(aso)
    return asos


@app.get('/asos/{aso_id}')
async def get_aso(aso_id: str) -> Optional[models.ASO]:
    '''Returns information about the ASO matching the passed ASO ID.'''
    return get_aso_from_oem(aso_id)


@app.get('/ephemeris/{aso_id}')
async def get_ephemeris(aso_id: str) -> Optional[models.OEMData]:
    '''Provides the most up-to-date ephemeris data for the given ASO'''
    aso_oem_data = oem_dataset.get(aso_id)
    return aso_oem_data
