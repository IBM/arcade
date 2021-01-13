from __future__ import annotations

from typing import List, Dict
from pydantic import BaseModel, validator
from orbdetpy import Frame  # type: ignore
from orbdetpy.utilities import interpolate_ephemeris  # type: ignore
import orbdetpy.conversion as conv  # type: ignore


class ASO(BaseModel):
    '''Model representing an anthropogenic space object (ASO).'''
    aso_id: str
    norad_id: str
    cospar_id: str
    aso_name: str


class EphemerisLine(BaseModel):
    '''A model for a single line of ephemeris data including the epoch and
    6-dimensional state vector.'''
    epoch: str
    state_vector: List[float]

    @validator('state_vector')
    def validate_state_vect(cls, val: List[float]) -> List[float]:
        '''Validates that the state vector has six components.'''
        if len(val) != 6:
            raise ValueError('State vector must be 6-dimensional')
        else:
            return val


class OEMData(BaseModel):
    '''A model representing the ephemeris data extracted from an OEM file for
    a single ASO.'''
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
        '''Validates that the reference frame is one that `orbdetpy`
        knows about.'''
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

    def interpolate(self, step_size: float, num_points: int = 5) -> OEMData:
        '''Interpolates the ephemeris data.

        :param step_size: The interpolated step size in seconds.
        :param num_points: The number of states to use for interpolation.
        '''
        epochs, state_vects = [], []
        for emph_line in self.ephemeris:
            epochs.append(emph_line.epoch)
            # Convert components from m and m\s to km and km\s
            state_vect = [i*1000.0 for i in emph_line.state_vector]
            state_vects.append(state_vect)
        offset_epochs = conv.get_J2000_epoch_offset(epochs)
        interpolation = interpolate_ephemeris(self.ref_frame,
                                              offset_epochs,
                                              state_vects,
                                              num_points,
                                              self.ref_frame,
                                              offset_epochs[0],
                                              offset_epochs[-1],
                                              step_size)
        interp_ephem_lines = []
        for proto_buf in interpolation:
            epoch = conv.get_UTC_string(proto_buf.time)
            state_vector = [i/1000.0 for i in list(proto_buf.true_state)]
            interp_ephem_line = EphemerisLine(epoch=epoch,
                                              state_vector=state_vector)
            interp_ephem_lines.append(interp_ephem_line)
        interp_oem_data = self.copy()
        interp_oem_data.ephemeris = interp_ephem_lines
        return interp_oem_data
