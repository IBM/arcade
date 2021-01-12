import gzip
import tarfile
from arcade.data_access.cos import COSBucket
from arcade.models import EphemerisLine, OEMData
from typing import List, Optional, Dict, Sequence, IO, Union


class COSOEMData:
    '''An interface for fetching and querying OEM data in cloud
    object storage.

    :param oem_bucket: The cloud object storage bucket where the OEM
        files are stored. Assumes the files are named in the format
        `YYYYMMDD_block_XX.tar`
    '''
    def __init__(self, oem_bucket: COSBucket) -> None:
        self.oem_bucket = oem_bucket
        self.date = self._get_latest_date()
        self.oem_data: Dict[str, OEMData] = dict()

    def _get_latest_date(self) -> str:
        '''Finds the date of the most recent OEM files.

        :return: The most recent OEM file date in the format
           `YYYYMMDD`
        '''
        oem_file_names = self.oem_bucket.list_file_names()
        dates = {f.split('_')[0] for f in oem_file_names}
        sorted_dates = sorted(dates, reverse=True)
        try:
            latest_date = sorted_dates[0]
            return latest_date
        except IndexError:
            return ''

    def _parse_oem_data(self, gz_file_obj: IO[bytes]) -> OEMData:
        '''Parses the OEM data from the passed gzip file.  Assumes there is
        only one ASO in each file.

        :param gz_file_obj: The file object for the gziped file.
        :return: The parsed OEM data
        '''
        with gzip.open(gz_file_obj, 'r') as gz_file:
            ephemeris_lines: List[EphemerisLine] = []
            raw_data: Dict['str', Union[str, List[EphemerisLine]]] = dict()
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
                    raw_data[k.lower()] = v
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
                    ephemeris_line = EphemerisLine(epoch=epoch,
                                                   state_vector=state_vector)
                    ephemeris_lines.append(ephemeris_line)
                    if epoch == raw_data['stop_time']:
                        section = 'covariance'
                # Currently we are not doing anything with the covariance data
                # and so we stop the parsing
                elif section == 'covariance':
                    break
        raw_data['ephemeris'] = ephemeris_lines
        oem_data = OEMData(**raw_data)
        return oem_data

    def _get_file_names_to_fetch(self, aso_ids:
                                 Sequence[str] = []) -> List[str]:
        '''Gets the file names that need to be fetched from the cloud object
        storage.

        :param aso_ids: An optional list of ASO IDs.  If present then only the
            file names containing those ASOs will be returned, otherwise
            returns all of the OEM files for the set date.
        :return: A list of the file names in the bucket that should be
            downloaded.
        '''
        if aso_ids:
            block_ids = {aso_id[:2] for aso_id in aso_ids}
            file_names_to_fetch = [f'{self.date}_block_{block_id}.tar'
                                   for block_id in block_ids]
        else:
            all_oem_files = self.oem_bucket.list_file_names()
            file_names_to_fetch = [f for f in all_oem_files
                                   if f.startswith(self.date)]
        return file_names_to_fetch

    def _get_gz_file_names(self,
                           tar_file: tarfile.TarFile,
                           aso_ids: Sequence[str]) -> Sequence[str]:
        '''Gets the names of the gzipped OEM files that need to be extracted
        from the tar file.

        :param tar_file: The tar file containing the gzipped OEM files
        :param aso_ids: An optional list of ASO ids.  If present then only
            gzipped OEM file names corresponding to the given ASOs will be
            returned, otherwise all OEM gzip files are returned.
        :return: The list of gzipped OEM files to extract from the tar file.
        '''
        member_names = [m.name for m in tar_file.getmembers()]
        gz_file_names = [m for m in member_names
                         if m.endswith('.gz')]
        if aso_ids:
            results = []
            for aso_id in aso_ids:
                for gz_file_name in gz_file_names:
                    if aso_id in gz_file_name:
                        results.append(gz_file_name)
        else:
            results = gz_file_names
        return results

    def _get_aso_id_from_file_name(self, filename: str) -> str:
        '''Extracts the ASO ID from the OEM gzip file name.

        :param filename: The OEM gzip file name
        :return: The ASO ID of the object referenced in the OEM file
        '''
        return filename.split('/')[-1].split('.')[0]

    def _extract_oem_tar_file(self,
                              tar_file_obj: IO[bytes],
                              aso_ids: Sequence[str]) -> None:
        '''Extracts and parses the OEM data from the given tar archive file.
        The results are stored in the instances `oem_data` attribute.

        :param tar_file_obj: The file object of the tar archive to extract OEM
            data out of
        :param aso_ids: The ASO ids to extract OEM data for out of the tar file
        '''
        with tarfile.open(fileobj=tar_file_obj) as tar_file:
            gz_file_names = self._get_gz_file_names(tar_file, aso_ids)
            for gz_file_name in gz_file_names:
                gz_file_obj = tar_file.extractfile(gz_file_name)
                if gz_file_obj:
                    oem_data = self._parse_oem_data(gz_file_obj)
                    aso_id = self._get_aso_id_from_file_name(gz_file_name)
                    self.oem_data[aso_id] = oem_data

    def get_oem_data_from_cos(self, aso_ids: Sequence[str] = [],
                              date: Optional[str] = None) -> None:
        '''Fetches, parses, and stores OEM data from the cloud object storage
        bucket.

        :param aso_ids: An optional list of ASO IDs to fetch the data for.  If
            no IDs are passed then data for all ASOs will be downloaded from
            the bucket.
        :param date: An optional date to fetch the data for.  If not present
            then use the latest date where data is present in the bucket.
        '''
        if date:
            self.date = date
        oem_tar_file_names = self._get_file_names_to_fetch(aso_ids)
        for tar_file_name in oem_tar_file_names:
            tar_file = self.oem_bucket.download_fileobj(tar_file_name)
            if tar_file:
                self._extract_oem_tar_file(tar_file, aso_ids)

    def get(self, aso_id: str) -> Optional[OEMData]:
        '''Returns the current ephemeris data for the given ASO ID.

        :param aso_id: The ID of the ASO to get the ephemeris data for.
        :return: The ephemeris data for the ASO
        '''
        return self.oem_data.get(aso_id)
