import gzip
import tarfile
from arcade.data_access.cos import COSBucket
from arcade.models import EphemerisLine, OEMData
from typing import List, Optional, Dict, Any, Sequence, IO


class COSOEMData:
    def __init__(self, oem_bucket: COSBucket) -> None:
        self.oem_bucket = oem_bucket
        self.date = self._get_latest_date()
        self.oem_data: Dict[str, OEMData] = dict()

    def _get_latest_date(self) -> str:
        oem_file_names = self.oem_bucket.list_file_names()
        dates = {f.split('_')[0] for f in oem_file_names}
        sorted_dates = sorted(dates, reverse=True)
        try:
            latest_date = sorted_dates[0]
            return latest_date
        except IndexError:
            return ''

    def _parse_oem_data(self, gz_file_obj: IO[bytes]) -> OEMData:
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
                    ephemeris_line = EphemerisLine(epoch=epoch,
                                                   state_vector=state_vector)
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
                    oem_data = self._parse_oem_data(gz_file_obj)
                    aso_id = self._get_aso_id_from_file_name(gz_file_name)
                    self.oem_data[aso_id] = oem_data

    def get_oem_data_from_cos(self, aso_ids: Sequence[str] = [],
                              date: Optional[str] = None) -> None:
        if date:
            self.date = date
        oem_tar_file_names = self._get_file_names_to_fetch(aso_ids)
        for tar_file_name in oem_tar_file_names:
            tar_file = self.oem_bucket.download_fileobj(tar_file_name)
            if tar_file:
                self._extract_oem_tar_file(tar_file, aso_ids)

    def get(self, aso_id: str) -> Optional[OEMData]:
        return self.oem_data.get(aso_id)
