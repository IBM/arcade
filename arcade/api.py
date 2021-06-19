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
import logging
import neomodel  # type: ignore
from typing import List, Optional
from fastapi import FastAPI
import arcade.models.graph as graph
import arcade.models.api as models


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

neomodel.config.DATABASE_URL = os.environ.get('NEO4J_BOLT_URL')

app = FastAPI(title='ARACADE')


@app.get('/asos')
async def get_asos() -> List[models.ASO]:
    '''Returns information on all the anthropogenic space objects (ASOs) that
    ARCADE knows about.
    '''
    aso_nodes = graph.SpaceObject.nodes.all()
    asos = [models.ASO.from_orm(n) for n in aso_nodes]
    return asos


@app.get('/asos/{aso_id}')
async def get_aso(aso_id: str) -> Optional[models.ASO]:
    '''Returns information about the ASO matching the passed ASO ID.'''
    aso_node = graph.SpaceObject.find(aso_id=aso_id)
    if not aso_node:
        return None
    aso = models.ASO.from_orm(aso_node)
    return aso


@app.get('/ephemeris/{aso_id}')
async def get_ephemeris(aso_id: str) -> Optional[models.OrbitEphemerisMessage]:
    '''Provides the most up-to-date ephemeris data for the given ASO'''
    oem_node = graph.SpaceObject.get_latest_oem(aso_id)
    if not oem_node:
        return None
    oem = models.OrbitEphemerisMessage.from_orm(oem_node)
    return oem


@app.get('/interpolate/{aso_id}')
async def get_interpolation(aso_id: str,
                            step_size: float = 60.0
                            ) -> Optional[models.OrbitEphemerisMessage]:
    '''Interpolates the ephemeris data for given ASP based on the step
    size (seconds).'''
    oem_node = graph.SpaceObject.get_latest_oem(aso_id)
    if not oem_node:
        return None
    oem = models.OrbitEphemerisMessage.from_orm(oem_node)
    interp_oem = oem.interpolate(step_size=step_size)
    return interp_oem
