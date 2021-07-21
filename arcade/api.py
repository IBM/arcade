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

import logging
import neomodel  # type: ignore
from typing import List, Optional
from pydantic import BaseSettings
from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTAuthentication
import arcade.models.graph as graph
import arcade.models.api as models


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Setup environment settings
class APISettings(BaseSettings):
    neo4j_url: str
    jwt_secret: str


settings = APISettings()

# Setup the database connection
neomodel.config.DATABASE_URL = settings.neo4j_url

# Tell fastpai_users how to interact with user data
user_db = graph.FastAPIUserDBAdapter(models.UserDB)

api_desc = ('The Advanced Research Collaboration and Application Development '
            'Environment (ARCADE) provides a unified and coherent API for '
            'accessing, analyzing, and extending a diverse set of derived '
            'data products concerning anthropogenic space objects.')
app = FastAPI(title='ARACADE', description=api_desc)


jwt_authentication = JWTAuthentication(
    secret=settings.jwt_secret,
    lifetime_seconds=3600,
    tokenUrl="auth/jwt/login"
)

# Setup fastapi_users to handle user CRUD, authentication, and authorization
fastapi_users = FastAPIUsers(
    user_db,
    [jwt_authentication],
    models.User,
    models.UserCreate,
    models.UserUpdate,
    models.UserDB
)

# Add the router for users to get JWTs
app.include_router(
    fastapi_users.get_auth_router(jwt_authentication),
    prefix="/auth/jwt",
    tags=["Authentication"]
)

# Add the router that provides the user registration endpoint
app.include_router(
    fastapi_users.get_register_router(),
    prefix="/auth",
    tags=["Authentication"],
    include_in_schema=False
)

# Helper functions that gets the user based on the JWT passed to the endpoint
current_active_user = fastapi_users.current_user(active=True)
current_super_user = fastapi_users.current_user(active=True, superuser=True)


@app.get('/',
         response_class=RedirectResponse,
         include_in_schema=False)
async def redirect_to_project() -> str:
    """Redirects the root path to the project website"""
    return 'https://ibm.github.io/arcade'


@app.get('/user_reports',
         response_model=List[models.UserReport],
         include_in_schema=False)
async def get_user_reports(user: models.User = Depends(current_super_user)
                           ) -> List[models.UserReport]:
    """Returns summary statistics for all users"""
    report_query = """MATCH (u:User)-[r:accessed]->()
                      RETURN u.email AS email, count(r) AS access_count"""
    raw_report, _ = neomodel.db.cypher_query(report_query)
    report_rows = [models.UserReport(email=row[0], access_count=row[1])
                   for row in raw_report]
    return report_rows


@app.get('/asos',
         response_model=List[models.ASO],
         tags=['ARCADE Endpoints'])
async def get_asos(user: models.User = Depends(current_active_user)
                   ) -> List[models.ASO]:
    """Returns information on all the anthropogenic space objects (ASOs) that
    ARCADE knows about.
    """
    aso_nodes = graph.SpaceObject.nodes.all()
    asos = [models.ASO.from_orm(n) for n in aso_nodes]
    return asos


@app.get('/asos/{aso_id}',
         response_model=models.ASO,
         tags=['ARCADE Endpoints'])
async def get_aso(aso_id: str,
                  user: models.User = Depends(current_active_user)
                  ) -> Optional[models.ASO]:
    """Returns information about the ASO matching the passed ASO ID."""
    aso_node = graph.SpaceObject.find_one(aso_id=aso_id)
    if not aso_node:
        return None
    aso = models.ASO.from_orm(aso_node)
    return aso


@app.get('/ephemeris/{aso_id}',
         response_model=List[models.OrbitEphemerisMessage],
         tags=['ARCADE Endpoints'])
async def get_ephemeris(aso_id: str,
                        user: models.User = Depends(current_active_user)
                        ) -> List[models.OrbitEphemerisMessage]:
    """Provides the most up-to-date ephemeris data for the given ASO"""
    oem_nodes = graph.SpaceObject.get_latest_oems(aso_id)
    if not oem_nodes:
        return []
    user_node = graph.User.find_one(uid=str(user.id))
    if not user_node:
        return []

    oems = []
    for oem_node in oem_nodes:
        if not user_node.can_access(oem_node):
            continue
        oem = models.OrbitEphemerisMessage.from_orm(oem_node)
        user_node.accessed.connect(oem_node, {'endpoint': '/ephemeris'})
        oems.append(oem)

    return oems


@app.get('/interpolate/{aso_id}',
         response_model=List[models.OrbitEphemerisMessage],
         tags=['ARCADE Endpoints'])
async def get_interpolation(aso_id: str,
                            step_size: float = 60.0,
                            user: models.User = Depends(current_active_user)
                            ) -> List[models.OrbitEphemerisMessage]:
    """Interpolates the ephemeris data for given ASP based on the step
    size (seconds)."""
    oem_nodes = graph.SpaceObject.get_latest_oems(aso_id)
    if not oem_nodes:
        return []
    user_node = graph.User.find_one(uid=str(user.id))
    if not user_node:
        return []

    interp_oems = []
    for oem_node in oem_nodes:
        if not user_node.can_access(oem_node):
            continue
        oem = models.OrbitEphemerisMessage.from_orm(oem_node)
        interp_oem = oem.interpolate(step_size=step_size)
        user_node.accessed.connect(oem_node, {'endpoint': '/interpolate'})
        interp_oems.append(interp_oem)

    return interp_oems


@app.get('/compliance/{aso_id}',
         response_model=models.UNCompliance,
         tags=['ARCADE Endpoints'])
async def get_compliance(aso_id: str,
                         user: models.User = Depends(current_active_user)
                         ) -> Optional[models.UNCompliance]:
    """Returns whether the ASO is compliant in registering with the United
    Nations."""
    aso_node = graph.SpaceObject.find_one(aso_id=aso_id)
    if not aso_node:
        return None
    compliance_nodes = aso_node.compliance.all()
    if compliance_nodes:
        compliance_node = compliance_nodes[0]
        print(compliance_node)
    else:
        return None
    user_node = graph.User.find_one(uid=str(user.id))
    if not user_node or not user_node.can_access(compliance_node):
        return None
    compliance = models.UNCompliance(aso_id=aso_id,
                                     is_compliant=compliance_node.is_compliant)
    user_node.accessed.connect(compliance_node, {'endpoint': '/compliance'})
    return compliance
