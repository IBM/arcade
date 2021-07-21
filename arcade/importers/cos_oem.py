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
import re
import logging
from typing import List, IO, Optional, Dict, Sequence, Union
import arcade.models.cos as cos
import arcade.models.graph as graph

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
logger = logging.getLogger(__name__)


EphemerisLine = Dict[str, Union[str, List[float]]]
OEMData = Dict[str, Union[str, List[EphemerisLine]]]


class BaseOEMCOSImporter:
    def __init__(self,
                 oem_bucket: cos.COSBucket,
                 data_source_name: str,
                 oem_file_fmt: str,
                 data_source_public: bool = True) -> None:
        self.oem_bucket = oem_bucket
        self.oem_file_fmt = oem_file_fmt
        self.bucket_node = self._get_bucket_node()
        self.data_source_node = graph.DataSource.get_or_create(
            {
                'name': data_source_name,
                'public': data_source_public
            }
        )[0]

    def _get_bucket_node(self) -> graph.COSBucket:
        """Gets or creates a neo4j node representing the COS bucket where the
        OEM files are stored.

        :return: The COS bucket node
        """
        bucket_node: Optional[graph.COSBucket]
        bucket_node = graph.COSBucket.nodes.first_or_none(
            name=self.oem_bucket.name
        )
        if bucket_node:
            return bucket_node
        else:
            new_bucket_node = graph.COSBucket(name=self.oem_bucket.name)
            new_bucket_node.save()
            return new_bucket_node

    def _get_files(self) -> Sequence[str]:
        """Gets the objects in the bucket that are the OEM files.

        :return: A list of all of the OEM file names.
        """
        all_files = self.oem_bucket.list_file_names()
        file_fmt = re.compile(self.oem_file_fmt)
        files = [f for f in all_files if file_fmt.search(f)]
        return files

    def _get_aso_node(self,
                      oem_data: OEMData,
                      aso_id: str) -> graph.SpaceObject:
        """Finds or creates a SpaceObject node in the graph.
        :param oem_data:  Data from the orbit ephemeris message that is used to
            create a SpaceObject node if one is not found
        :param aso_id: The ID of the ASO to find in the graph
        :return: A SpaceObject neo4j node instance
        """
        aso_node = graph.SpaceObject.find_one(aso_id=aso_id)
        if aso_node:
            return aso_node
        else:
            new_aso_node = graph.SpaceObject(
                aso_id=aso_id,
                norad_id=aso_id,
                cospar_id=oem_data.get('object_id'),
                name=oem_data.get('object_name')
            )
            new_aso_node.save()
            return new_aso_node

    def _get_cos_object_node(self, object_name: str) -> graph.COSObject:
        """Gets or creates the node in the graph representing the cloud object
        storage object
        :param object_name: The name of the COS object in the instance's OEM
            bucket
        :return: The ne4j COS object node instance
        """
        object_node: Optional[graph.COSObject]
        object_node = self.bucket_node.objects \
                          .filter(name=object_name) \
                          .first_or_none()
        if object_node:
            return object_node
        else:
            new_object_node = graph.COSObject(name=object_name, imported=False)
            new_object_node.save()
            new_object_node.bucket.connect(self.bucket_node)
            return new_object_node

    def _save_oem(self,
                  oem_data: OEMData,
                  aso_id: str,
                  object_node: graph.COSObject) -> None:
        """Saves the orbit ephemeris message in the graph.

        :param oem_data: The data in the orbit ephemeris message
        :param aso_id: The ID of the space object the OEM pertains to
        :param object_node: The node in the graph representing the COS object
           the OEM is stored in
        """
        aso_node = self._get_aso_node(oem_data, aso_id)
        # Clean out old OEM messages attached to the ASO node
        oem_date = oem_data['stop_time']
        old_oems = [oem for oem in aso_node.ephemeris_messages.all()
                    if self.data_source_node in oem.from_data_source.all()]
        for old_oem in old_oems:
            if old_oem.stop_time < oem_date:
                old_oem.delete()
            else:
                return None
        # Create a new OEM node
        oem_node = graph.OrbitEphemerisMessage(**oem_data)
        oem_node.save()
        # Link the OEM node to the ASO, data source, and COS object nodes
        oem_node.from_data_source.connect(self.data_source_node)
        oem_node.in_cos_object.connect(object_node)
        aso_node.ephemeris_messages.connect(oem_node)

    def _process_fileobj(self,
                         fileobj: IO[bytes],
                         object_node: graph.COSObject) -> None:
        raise NotImplementedError

    def run(self) -> None:
        """Fetches, parses, and stores OEM data from the cloud object storage
        bucket.
        """
        files = self._get_files()
        for f in files:
            object_node = self._get_cos_object_node(f)
            if object_node.imported:
                continue
            logger.info(f'Fetching file {f} from COS...')
            fileobj = self.oem_bucket.download_fileobj(f)
            try:
                if not fileobj:
                    continue
                logger.info(f'Processing file {f}...')
                self._process_fileobj(fileobj, object_node)
                object_node.imported = True
                object_node.save()
            except Exception as e:
                logger.error(f'Could not process tarfile {f}, Error: {e}')
