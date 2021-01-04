from typing import List
from pydantic import BaseModel


class ASO(BaseModel):
    aso_id: str
    norad_id: str
    cospar_id: str
    aso_name: str


class EphemerisLine(BaseModel):
    epoch: str
    state_vector: List[float]


class OEMData(BaseModel):
    ephemeris: List[EphemerisLine]
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
