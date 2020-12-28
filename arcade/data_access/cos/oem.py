import io
import gzip
import tarfile
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Sequence, IO
from ibm_boto3.resources.base import ServiceResource  # type: ignore


@dataclass
class EphemerisLine:
    epoch: str
    state_vector: Sequence[float]


@dataclass
class OEMData:
    ephemeris: Sequence[EphemerisLine]
    ccsds_oem_vers: str
    creation_date: str
    originator: str
    object_name: str
    object_id: str
    center_name: str
    ref_frame: str
    time_system: str
    start_time: str
    stop_time: str


class COSOEMData:
    def __init__(self, cos_client: ServiceResource, cos_bucket: str) -> None:
        self.cos_client = cos_client
        self.cos_bucket = cos_bucket
        self.oem_date = self._get_latest_date()
        self.oem_data: Dict[str, OEMData] = dict()

    def _get_oem_file_names(self) -> List[str]:
        oem_bucket = self.cos_client.Bucket(self.cos_bucket)
        oem_files = oem_bucket.objects.all()
        return [f.key for f in oem_files]

    def _get_latest_date(self) -> str:
        oem_file_names = self._get_oem_file_names()
        dates = {f.split('_')[0] for f in oem_file_names}
        sorted_dates = sorted(dates, reverse=True)
        try:
            latest_date = sorted_dates[0]
            return latest_date
        except IndexError:
            return ''

    def parse_oem_data(self, gz_file_obj: IO[bytes]) -> OEMData:
        with gzip.open(gz_file_obj, 'r') as gz_file:
            ephemeris_lines: List[EphemerisLine] = []
            raw_data: Dict['str', Any] = dict()
            section = 'header'
            for raw_line in gz_file:
                line = raw_line.decode('utf-8')
                # Skip blank or comment lines
                if len(line) == 0 or line.startswith('COMMENT'):
                    continue
                elif '=' in line:
                    k, v = [s.strip() for s in line.split('=')]
                    raw_data[k.lower()] = v
                elif line.startswith('META_START'):
                    section = 'meta'
                elif line.startswith('META_STOP'):
                    section = 'ephemeris'
                elif section == 'ephemeris':
                    line_data = line.split(' ')
                    epoch = line_data[0]
                    state_vector = [float(s) for s in line_data[1:]]
                    ephemeris_line = EphemerisLine(epoch, state_vector)
                    ephemeris_lines.append(ephemeris_line)
                    if epoch == raw_data['stop_time']:
                        section = 'covariance'
                elif section == 'covariance':
                    break
        raw_data['ephemeris'] = ephemeris_lines
        oem_data = OEMData(**raw_data)
        return oem_data

    def _get_file_names_to_fetch(self, aso_ids:
                                 Sequence[str] = []) -> List[str]:
        if aso_ids:
            block_ids = {aso_id[:2] for aso_id in aso_ids}
            file_names_to_fetch = [f'{self.oem_date}_block_{block_id}.tar'
                                   for block_id in block_ids]
        else:
            all_oem_files = self._get_oem_file_names()
            file_names_to_fetch = [f for f in all_oem_files
                                   if f.startswith(self.oem_date)]
        return file_names_to_fetch

    def _get_gz_file_names(self,
                           tar_file: tarfile.TarFile,
                           aso_ids: Sequence[str]) -> Sequence[str]:
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
        return filename.split('/')[-1].split('.')[0]

    def _extract_oem_tar_file(self,
                              tar_file_obj: IO[bytes],
                              aso_ids: Sequence[str]) -> None:
        with tarfile.open(fileobj=tar_file_obj) as tar_file:
            gz_file_names = self._get_gz_file_names(tar_file, aso_ids)
            for gz_file_name in gz_file_names:
                gz_file_obj = tar_file.extractfile(gz_file_name)
                if gz_file_obj:
                    oem_data = self.parse_oem_data(gz_file_obj)
                    aso_id = self._get_aso_id_from_file_name(gz_file_name)
                    self.oem_data[aso_id] = oem_data

    def _fetch_tar_file(self, tar_file_name: str) -> IO[bytes]:
        tar_cos_ref = self.cos_client.Object(self.cos_bucket,
                                             tar_file_name).get()
        tar_bytes = tar_cos_ref['Body'].read()
        tar_file_obj = io.BytesIO(tar_bytes)
        return tar_file_obj

    def get_oem_data_from_cos(self, aso_ids: Sequence[str] = [],
                              date: Optional[str] = None) -> None:
        if date:
            self.oem_date = date
        oem_tar_file_names = self._get_file_names_to_fetch(aso_ids)
        for tar_file_name in oem_tar_file_names:
            tar_file = self._fetch_tar_file(tar_file_name)
            self._extract_oem_tar_file(tar_file, aso_ids)
