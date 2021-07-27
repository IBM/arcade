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
import gzip
import logging
import tarfile
from typing import List, IO
import arcade.models.cos as cos
import arcade.models.graph as graph
from arcade.importers.cos_oem.cos_oem import (BaseOEMCOSImporter,
                                              OEMData, EphemerisLine)

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
logger = logging.getLogger(__name__)


class UTOEMCOSImporter(BaseOEMCOSImporter):
    """A class for fetching OEM data from UT in cloud object storage and
    loading it into neo4j.

    :param oem_bucket: The COS bucket where the OEM files are stored
    """
    def __init__(self, oem_bucket: cos.COSBucket) -> None:
        super().__init__(oem_bucket,
                         data_source_name='UT - OEM',
                         oem_file_fmt='[0-9]{8}_block_[0-9]{2}.tar',
                         data_source_public=True)

    def _parse_oem_data(self, gz_file_obj: IO[bytes]) -> OEMData:
        """Parses the OEM data from the passed gzip file.  Assumes there is
        only one ASO in each file.

        :param gz_file_obj: The file object for the gziped file.
        :return: The parsed OEM data
        """
        with gzip.open(gz_file_obj, 'r') as gz_file:
            ephemeris_lines: List[EphemerisLine] = []
            oem_data: OEMData = dict()
            # First section of the file is a header section.
            section = 'header'
            for raw_line in gz_file:
                line = raw_line.decode('utf-8').strip()
                # Skip blank or comment lines
                if len(line) == 0 or line.startswith('COMMENT'):
                    continue
                # Parses a line that has a property and corresponding value
                elif '=' in line:
                    k, v = [s.strip() for s in line.split('=')]
                    oem_data[k.lower()] = v
                # Start parsing the metadata section
                elif line.startswith('META_START'):
                    section = 'meta'
                # The metadata is done, start parsing the ephemeris lines
                elif line.startswith('META_STOP'):
                    section = 'ephemeris'
                elif section == 'ephemeris':
                    line_data = line.split(' ')
                    epoch = line_data[0]
                    state_vector = [float(s) for s in line_data[1:]]
                    ephemeris_line: EphemerisLine
                    ephemeris_line = dict(epoch=epoch,
                                          state_vector=state_vector)
                    ephemeris_lines.append(ephemeris_line)
                    if epoch == oem_data['stop_time']:
                        section = 'covariance'
                # Currently we are not doing anything with the covariance data
                # and so we stop the parsing
                elif section == 'covariance':
                    break
        oem_data['ephemeris_lines'] = ephemeris_lines
        return oem_data

    def _get_aso_id_from_file_name(self, filename: str) -> str:
        """Extracts the ASO ID from the OEM gzip file name.

        :param filename: The OEM gzip file name
        :return: The ASO ID of the object referenced in the OEM file
        """
        id_parts = filename.split('/')
        prefix = id_parts[1]
        suffix = id_parts[-1].split('.')[0].zfill(3)
        if len(suffix) == 5:
            return suffix
        else:
            return prefix + suffix

    def _process_fileobj(self,
                         tar_file_obj: IO[bytes],
                         object_node: graph.COSObject) -> None:
        """Extracts and parses the OEM data from the given tar archive file.

        :param tar_file_obj: The file object of the tar archive to extract OEM
            data out of
       :param object_node: The node in the graph representing the COS object
           the OEM is stored in
        """
        with tarfile.open(fileobj=tar_file_obj) as tar_file:
            gz_file_names = [f.name for f in tar_file.getmembers()
                             if f.name.endswith('.gz')]
            for gz_file_name in gz_file_names:
                gz_file_obj = tar_file.extractfile(gz_file_name)
                if gz_file_obj:
                    oem_data = self._parse_oem_data(gz_file_obj)
                    aso_id = self._get_aso_id_from_file_name(gz_file_name)
                    self._save_oem(oem_data, aso_id, object_node)
