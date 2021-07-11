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
from fastapi import FastAPI, Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTAuthentication
import arcade.models.graph as graph
import arcade.models.api as models


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

neomodel.config.DATABASE_URL = os.environ.get('NEO4J_BOLT_URL')

user_db = graph.FastAPIUserDBAdapter(models.UserDB)

app = FastAPI(title='ARACADE')


jwt_authentication = JWTAuthentication(
    secret=os.environ['JWT_SECRET'],
    lifetime_seconds=3600,
    tokenUrl="auth/jwt/login"
)

fastapi_users = FastAPIUsers(
    user_db,
    [jwt_authentication],
    models.User,
    models.UserCreate,
    models.UserUpdate,
    models.UserDB
)

app.include_router(
    fastapi_users.get_auth_router(jwt_authentication),
    prefix="/auth/jwt",
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["auth"],

)

current_active_user = fastapi_users.current_user(active=True)


@app.get('/asos', response_model=List[models.ASO])
async def get_asos(user: models.User = Depends(current_active_user)
                   ) -> List[models.ASO]:
    """Returns information on all the anthropogenic space objects (ASOs) that
    ARCADE knows about.
    """
    aso_nodes = graph.SpaceObject.nodes.all()
    asos = [models.ASO.from_orm(n) for n in aso_nodes]
    return asos


@app.get('/asos/{aso_id}', response_model=models.ASO)
async def get_aso(aso_id: str,
                  user: models.User = Depends(current_active_user)
                  ) -> Optional[models.ASO]:
    """Returns information about the ASO matching the passed ASO ID."""
    aso_node = graph.SpaceObject.find(aso_id=aso_id)
    if not aso_node:
        return None
    aso = models.ASO.from_orm(aso_node)
    return aso


@app.get('/ephemeris/{aso_id}', response_model=models.OrbitEphemerisMessage)
async def get_ephemeris(aso_id: str,
                        user: models.User = Depends(current_active_user)
                        ) -> Optional[models.OrbitEphemerisMessage]:
    """Provides the most up-to-date ephemeris data for the given ASO"""
    oem_node = graph.SpaceObject.get_latest_oem(aso_id)
    if not oem_node:
        return None
    oem = models.OrbitEphemerisMessage.from_orm(oem_node)
    return oem


@app.get('/interpolate/{aso_id}', response_model=models.OrbitEphemerisMessage)
async def get_interpolation(aso_id: str,
                            step_size: float = 60.0,
                            user: models.User = Depends(current_active_user)
                            ) -> Optional[models.OrbitEphemerisMessage]:
    """Interpolates the ephemeris data for given ASP based on the step
    size (seconds)."""
    oem_node = graph.SpaceObject.get_latest_oem(aso_id)
    if not oem_node:
        return None
    oem = models.OrbitEphemerisMessage.from_orm(oem_node)
    interp_oem = oem.interpolate(step_size=step_size)
    return interp_oem
