from typing import List, Dict
from pydantic import BaseModel, validator
from orbdetpy import Frame  # type: ignore
from orbdetpy.utilities import interpolate_ephemeris  # type: ignore
from orbdetpy.conversion import get_J2000_epoch_offset  # type: ignore


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

    @validator('ref_frame')
    def validate_frame(cls, val: str) -> str:
        frame_map: Dict[str, str]
        frame_map = {
            'EME2000': Frame.EME2000,
            'GCRF': Frame.GCRF,
            'ICRF': Frame.ICRF,
            'ITRF2000': Frame.ITRF_CIO_CONV_2003_ACCURATE_EOP,
            'ITRF-93': Frame.ITRF_CIO_CONV_1996_ACCURATE_EOP,
            'ITRF-97': Frame.ITRF_CIO_CONV_1996_ACCURATE_EOP,
            'TEME': Frame.TEME,
            'TOD': Frame.TOD_CONVENTIONS_2010_ACCURATE_EOP
        }
        if val not in frame_map:
            raise ValueError('Unknown reference frame')
        return frame_map[val]

    def interopolate(self, step_size: float, degree: int = 5) -> None:
        epochs, state_vects = [], []
        for emph_line in self.ephemeris:
            epochs.append(emph_line.epoch)
            state_vect = [i*1000.0 for i in emph_line.state_vector]
            state_vects.append(state_vect)
        offset_epochs = get_J2000_epoch_offset(epochs)
        interpolation: None
        interpolation = interpolate_ephemeris(self.ref_frame,
                                              offset_epochs,
                                              state_vects,
                                              degree,
                                              self.ref_frame,
                                              offset_epochs[0],
                                              offset_epochs[-1],
                                              step_size)
        return interpolation
