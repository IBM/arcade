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
import logging
import zipfile
from typing import List, IO, Tuple
from datetime import datetime
import arcade.models.cos as cos
import arcade.models.graph as graph
from arcade.importers.cos_oem.cos_oem import (BaseOEMCOSImporter,
                                              OEMData, EphemerisLine)

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
logger = logging.getLogger(__name__)


class StarlinkOEMCOSImporter(BaseOEMCOSImporter):
    """A class for fetching OEM data from the Starlink constellation in cloud
    object storage and loading it into neo4j.

    :param oem_bucket: The COS bucket where the OEM files are stored
    """
    def __init__(self, oem_bucket: cos.COSBucket) -> None:
        super().__init__(oem_bucket,
                         data_source_name='Starlink - OEM',
                         oem_file_fmt='[0-9]{20}.oem',
                         data_source_public=True)

    def _convert_header_time(self, time_str: str) -> str:
        """Converts the time strings in the header of the Starlink OEM files
        into the standard format used in the graph.

        :param time_str: The time string to conver
        :return: The normalized time string
        """
        input_time_fmt = '%Y-%m-%d %H:%M:%S %Z'
        output_time_fmt = '%Y-%m-%dT%H:%M:%S'
        dt_obj = datetime.strptime(time_str.strip(), input_time_fmt)
        return dt_obj.strftime(output_time_fmt)

    def _convert_ephem_time(self, time_str: str) -> str:
        """Converts the epoch time strings in the ephemeris lines of the
        Starlink OEM files into the standard format used in the graph.

        :param time_str: The time string to conver
        :return: The normalized time string
        """
        input_time_fmt = '%Y%j%H%M%S.%f'
        output_time_fmt = '%Y-%m-%dT%H:%M:%S.%f'
        dt_obj = datetime.strptime(time_str.strip(), input_time_fmt)
        return dt_obj.strftime(output_time_fmt)

    def _parse_oem_data(self,
                        zip_file: zipfile.ZipFile,
                        oem_file_name: str) -> OEMData:
        """Parses the OEM data in text file contained in the passed zip
        archive.

        :param zip_file: The zip archive containing the OEM text files
        :param oem_file_name: The text file in the zip archive to parse

        return: The parsed OEM data
        """
        ephemeris_lines: List[EphemerisLine] = []
        # Message data not contained in the OEM files
        oem_data: OEMData = {
            'originator': 'Starlink',
            'center_name': 'EARTH',
            'ref_frame': 'EME2000',
            'time_system': 'UTC'
        }
        with io.TextIOWrapper(zip_file.open(oem_file_name),
                              encoding='utf8') as oem_file:
            for line_no, line in enumerate(oem_file):
                if len(line.strip()) == 0:
                    break
                # Header information is on the first 2 lines of the file
                if line_no == 0:
                    ts = line[8:]
                    oem_data['creation_date'] = self._convert_header_time(ts)
                elif line_no == 1:
                    start = line[16:39]
                    stop = line[55:78]
                    oem_data['start_time'] = self._convert_header_time(start)
                    oem_data['stop_time'] = self._convert_header_time(stop)
                else:
                    # The state vectors are on every 4th line
                    if not line_no % 4 == 0:
                        continue
                    ephem_data = line.split(' ')
                    epoch = self._convert_ephem_time(ephem_data[0])
                    state_vector = [float(s) for s in ephem_data[1:]]
                    ephemeris_line: EphemerisLine
                    ephemeris_line = dict(epoch=epoch,
                                          state_vector=state_vector)
                    ephemeris_lines.append(ephemeris_line)
            oem_data['ephemeris_lines'] = ephemeris_lines
        return oem_data

    def _get_aso_id_name(self, file_name: str) -> Tuple[str, str]:
        """Gets the Starlink satellite's name and NORAD ID from the text
        file name.

        :param file_name: The name of the text file containing the OEM data
        :return: The NORAD ID and name of the satellite
        """
        data_parts = file_name.split('_')
        aso_id = data_parts[1]
        object_name = data_parts[2]
        return aso_id, object_name

    def _process_fileobj(self,
                         fileobj: IO[bytes],
                         object_node: graph.COSObject) -> None:
        """Extracts and parses the OEM data from the given tar archive file.

        :param tar_file_obj: The file object of the tar archive to extract OEM
            data out of
       :param object_node: The node in the graph representing the COS object
           the OEM is stored in
        """
        with zipfile.ZipFile(fileobj) as zip_file:
            txt_file_names = [f for f in zip_file.namelist()
                              if f.endswith('.txt')]
            for txt_file_name in txt_file_names:
                oem_data = self._parse_oem_data(zip_file, txt_file_name)
                aso_id, object_name = self._get_aso_id_name(txt_file_name)
                oem_data['object_name'] = object_name
                self._save_oem(oem_data, aso_id, object_node)
