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
import gzip
import tarfile
from typing import List, IO, Optional, Dict, Sequence, Union
import neomodel  # type: ignore
import arcade.models.cos as cos
import arcade.models.graph as graph
from arcade.models.cos import IBMBucket

EphemerisLine = Dict[str, Union[str, List[float]]]
OEMData = Dict[str, Union[str, List[EphemerisLine]]]


class UTOEMCOSImporter:
    """An interface for fetching OEM data from UT in cloud object storage and
    loading it into neo4j.

    :param oem_bucket: The cloud object storage bucket where the OEM
        files from UT are stored. Assumes the files are named in the format
        `YYYYMMDD_block_XX.tar`
    """
    def __init__(self, oem_bucket: IBMBucket) -> None:
        self.oem_bucket = oem_bucket
        self.bucket_node = self._get_bucket_node()
        self.collection_node = graph.Collection.nodes.first(name='UT - OEM')

    def _get_bucket_node(self) -> graph.COSBucket:
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

    def _get_ut_files(self) -> Sequence[str]:
        all_files = self.oem_bucket.list_file_names()
        ut_file_fmt = re.compile('[0-9]{8}_block_[0-9]{2}.tar')
        ut_files = [f for f in all_files if ut_file_fmt.search(f)]
        return ut_files

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

    def _get_gz_file_names(self, tar_file: tarfile.TarFile) -> Sequence[str]:
        """Gets the names of the gzipped OEM files that need to be extracted
        from the tar file.

        :param tar_file: The tar file containing the gzipped OEM files
        :return: The list of gzipped OEM files to extract from the tar file.
        """
        member_names = [m.name for m in tar_file.getmembers()]
        gz_file_names = [m for m in member_names
                         if m.endswith('.gz')]
        return gz_file_names

    def _get_aso_id_from_file_name(self, filename: str) -> str:
        """Extracts the ASO ID from the OEM gzip file name.

        :param filename: The OEM gzip file name
        :return: The ASO ID of the object referenced in the OEM file
        """
        id_parts = filename.split('/')
        prefix = id_parts[1]
        suffix = id_parts[-1].split('.')[0].zfill(3)
        return prefix + suffix

    def _get_aso_node(self,
                      oem_data: OEMData,
                      aso_id: str) -> graph.SpaceObject:
        aso_node = graph.SpaceObject.find(aso_id=aso_id)
        if aso_node:
            return aso_node
        else:
            new_aso_node = graph.SpaceObject(aso_id=aso_id,
                                             norad_id=aso_id,
                                             cospar_id=oem_data['object_id'],
                                             name=oem_data['object_name'])
            new_aso_node.save()
            return new_aso_node

    def _save_oem(self,
                  oem_data: OEMData,
                  aso_id: str,
                  object_node: graph.COSObject) -> None:
        aso_node = self._get_aso_node(oem_data, aso_id)
        # Clean out old OEM messages attached to the ASO node
        oem_date = oem_data['stop_time']
        old_oems = aso_node.ephemeris_messages.all()
        for old_oem in old_oems:
            if old_oem.stop_time < oem_date:
                old_oem.delete()
        # Create a new OEM node
        oem_node = graph.OrbitEphemerisMessage(**oem_data)
        oem_node.save()
        # Link the OEM node to the ASO, collection and COS object nodes
        oem_node.from_collection.connect(self.collection_node)
        oem_node.in_cos_object.connect(object_node)
        aso_node.ephemeris_messages.connect(oem_node)

    def _extract_oem_tar_file(self,
                              tar_file_obj: IO[bytes],
                              object_node: graph.COSObject) -> None:
        """Extracts and parses the OEM data from the given tar archive file.
        The results are stored in the instances `oem_data` attribute.

        :param tar_file_obj: The file object of the tar archive to extract OEM
            data out of
        """
        with tarfile.open(fileobj=tar_file_obj) as tar_file:
            gz_file_names = self._get_gz_file_names(tar_file)
            for gz_file_name in gz_file_names:
                gz_file_obj = tar_file.extractfile(gz_file_name)
                if gz_file_obj:
                    oem_data = self._parse_oem_data(gz_file_obj)
                    aso_id = self._get_aso_id_from_file_name(gz_file_name)
                    self._save_oem(oem_data, aso_id, object_node)

    def _get_cos_object_node(self, object_name: str) -> graph.COSObject:
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

    def import_oem_data_from_cos(self) -> None:
        """Fetches, parses, and stores OEM data from the cloud object storage
        bucket.
        """
        ut_files = self._get_ut_files()
        for f in ut_files:
            object_node = self._get_cos_object_node(f)
            if object_node.imported:
                continue
            tar_file = self.oem_bucket.download_fileobj(f)
            if tar_file:
                self._extract_oem_tar_file(tar_file, object_node)
                object_node.imported = True
                object_node.save()


def seed_graph() -> None:
    graph.Collection.get_or_create(
        {
            'name': 'UT - OEM',
            'public': True
        }
    )


if __name__ == '__main__':
    cos_client = cos.build_cos_client()
    bucket = IBMBucket(cos_client, os.environ['COS_BUCKET'])
    neomodel.config.DATABASE_URL = os.environ['NEO4J_BOLT_URL']
    seed_graph()
    importer = UTOEMCOSImporter(bucket)
    importer.import_oem_data_from_cos()
