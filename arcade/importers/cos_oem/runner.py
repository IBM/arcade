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

import os
import time
import logging
import neomodel  # type: ignore
import arcade.models.cos as cos
from arcade.importers.cos_oem.ut_oem import UTOEMCOSImporter
from arcade.importers.cos_oem.starlink_oem import StarlinkOEMCOSImporter


logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    cos_client = cos.build_cos_client()
    bucket_name = os.environ['COS_BUCKET']
    bucket = cos.IBMBucket(cos_client, bucket_name)
    neomodel.config.DATABASE_URL = os.environ['NEO4J_URL']

    ut_importer = UTOEMCOSImporter(bucket)
    starlink_importer = StarlinkOEMCOSImporter(bucket)
    importers = [ut_importer, starlink_importer]

    logger.info('Starting all importers...')
    while True:
        for importer in importers:
            importer.run()
        logger.info('Importers Finished, sleeping 1 hour...')
        time.sleep(3600)
