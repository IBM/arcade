import os
import logging
from typing import List, Optional
from fastapi import FastAPI
import arcade.data_access.cos as cos
import arcade.models as models
from arcade.data_access.cos.oem import COSOEMData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ['DEV'] = 'True'


def build_oem_data() -> COSOEMData:
    oem_bucket: cos.COSBucket
    if os.environ.get('DEV'):
        oem_bucket = cos.TestBucket()
    else:
        cos_client = cos.build_cos_client()
        oem_bucket_name = os.environ.get('COS_BUCKET', '')
        oem_bucket = cos.Bucket(cos_client, oem_bucket_name)
    cos_oem_data = COSOEMData(oem_bucket)
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

app = FastAPI()


def get_aso_from_oem(aso_id: str) -> Optional[models.ASO]:
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
    return get_aso_from_oem(aso_id)


@app.get('/ephemeris/{aso_id}')
async def get_ephemeris(aso_id: str) -> Optional[models.OEMData]:
    aso_oem_data = oem_dataset.get(aso_id)
    return aso_oem_data
