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

from __future__ import annotations
from typing import Optional, TypeVar, Type, Dict, Union

from aioify import aioify  # type: ignore

from neomodel import (StringProperty, EmailProperty,  # type: ignore
                      JSONProperty, BooleanProperty, UniqueIdProperty,
                      DateTimeProperty)
from neomodel import (StructuredNode, RelationshipTo, RelationshipFrom,
                      StructuredRel)

from pydantic import UUID4
from fastapi_users.models import UD
from fastapi_users.db.base import BaseUserDatabase


NodeType = TypeVar('NodeType', bound='StructuredNode')


class FindMixin:
    """A mixin that provides convenient functions for finding instances
    of nodes in the graph."""
    @classmethod
    def find_one(cls: Type[NodeType], **kwargs: str) -> Optional[NodeType]:
        """Finds the first node of type `cls` matching the `kwargs`.
        Returns `None` if no node is matched."""
        node: NodeType = cls.nodes.first_or_none(**kwargs)
        return node


class FastAPIUserDBAdapter(BaseUserDatabase[UD]):
    """A database adapter that allows the `fastapi_users` library to use neo4j
    as a backend.

    :param user_db_model: The pydantic model representing how a user is stored
        in the database
    """
    def __init__(self, user_db_model: Type[UD]):
        super().__init__(user_db_model)

    @aioify
    def get(self, uid: UUID4) -> Optional[UD]:
        """Retrieves a user node by its unique ID, returns `None` if no user is
        found for the provided UUID.

        :param uid: The unique ID for the user node
        """
        user = User.find_one(uid=str(uid))
        if user:
            return self.user_db_model(**user.to_dict())
        else:
            return None

    @aioify
    def get_by_email(self, email: str) -> Optional[UD]:
        """Retrieves a user node by its email address, returns `None` if no
        user is found for the provided email.

        :param email: The email address of the user node
        """
        user = User.find_one(email=email)
        if user:
            return self.user_db_model(**user.to_dict())
        else:
            return None

    @aioify
    def create(self, user: UD) -> UD:
        """Creates a user node using the data in the pydantic model.

        :param user: pydantic model containing the user's data
        """
        user_dict = user.dict()
        # The fastapi_users library requires that the database record use the
        # `id` property for the user's UUID, however neo4j internally uses the
        # `id` property as an incrementing integer.  Here we store the
        # fastapi_users UUID as the `uid` property and remove the `id` field
        # before storing in neo4j.
        user_dict['uid'] = user_dict.pop('id')
        User(**user_dict).save()
        return user

    @aioify
    def update(self, user: UD) -> UD:
        """Updates a user node with the data in the provided pydantic model

        :param user: pydantic model containing the user's data
        """
        user = User.create_or_update(user.dict())
        return user

    @aioify
    def delete(self, user: UD) -> None:
        """Deletes a user node from the graph.

        :param user: pydantic model containing the user's data
        """
        user_node = User.find_one(uid=str(user.id))
        if user_node:
            user_node.delete()


class AccessRel(StructuredRel):  # type: ignore
    """The relationship that models when and what data a user accessed through
    the API.
    (User)-[:accessed]->(BaseAccess)
    """
    # The timestamp when the user accessed the data
    time = DateTimeProperty(default_now=True)
    # The API endpoint the user used to access the data
    endpoint = StringProperty(required=True)


class BaseAccess(StructuredNode):  # type: ignore
    """An abstract node type the keeps track of when a user accessed a certain
    node.  All node types that want user access tracked should inherit from
    this class."""
    __abstract_node__ = True
    from_data_source = RelationshipTo('DataSource', 'from_data_source')
    accessed_by = RelationshipFrom('User', 'accessed', model=AccessRel)


class User(StructuredNode, FindMixin):  # type: ignore
    """A `neomodel` model specifying how a user is stored in neo4j."""
    uid = UniqueIdProperty()
    email = EmailProperty(unique_index=True, required=True)
    hashed_password = StringProperty(required=True)
    is_active = BooleanProperty()
    is_verified = BooleanProperty()
    is_superuser = BooleanProperty()

    data_sources = RelationshipTo('DataSource', 'has_access')
    accessed = RelationshipTo('BaseAccess',
                              'accessed',
                              model=AccessRel)

    def post_create(self) -> None:
        """Hook that is run after a user node is created"""
        self._add_public_data_sources()

    def _add_public_data_sources(self) -> None:
        """Links the user node to have access to all public data source
        nodes"""
        public_data_sources = DataSource.nodes.filter(public=True)
        for pds in public_data_sources:
            self.data_sources.connect(pds)

    def to_dict(self) -> Dict[str, Union[str, bool]]:
        """Converts the user node to a dictionary representation and renames
        the `uid` key to the `id` key so that the resulting dict can be
        converted to a fastapi_users pydantic user model."""
        d = self.__dict__.copy()
        d['id'] = d.pop('uid')
        return d

    def can_access(self, node: BaseAccess) -> bool:
        """Uses the `has_access` relationship to determine if the user has
        permission to access data from a specific data source.

        :param node: The node instance that the user wants to access
        """
        node_source = node.from_data_source.all()[0]
        user_sources = self.data_sources.all()
        # Checks that the data source the `node` came from is one in which the
        # user has access to
        return node_source in user_sources


class DataSource(StructuredNode):  # type: ignore
    """A `neomodel` model representing a data source that data
    originates from."""
    name = StringProperty(unique_index=True, required=True)
    public = BooleanProperty()


class COSBucket(StructuredNode):  # type: ignore
    """A `neomodel` model representing a cloud object storage bucket used in
    tracking data provenance."""
    name = StringProperty(unique_index=True, required=True)

    objects = RelationshipFrom('COSObject', 'in_bucket')


class COSObject(StructuredNode):  # type: ignore
    """A `neomodel` model representing an object inside of a cloud object
    storage bucket used in tracking data provenance."""
    name = StringProperty(unique_index=True, required=True)
    imported = BooleanProperty()

    bucket = RelationshipTo('COSBucket', 'in_bucket')


class SpaceObject(StructuredNode, FindMixin):  # type: ignore
    """A `neomodel` model representing an anthropogenic space object."""
    aso_id = StringProperty(unique_index=True, required=True)
    norad_id = StringProperty(unique_index=True, required=True)
    cospar_id = StringProperty()
    name = StringProperty()

    ephemeris_messages = RelationshipTo('OrbitEphemerisMessage', 'has_oem')
    compliance = RelationshipTo('Compliance', 'has_compliance')

    @classmethod
    def get_latest_oem(cls, aso_id: str) -> Optional[OrbitEphemerisMessage]:
        """Gets the most recent orbit ephemeris message for an ASO

        :param aso_id: The ID of the ASO to find the most recent OEM for
        """
        aso_node = cls.find_one(aso_id=aso_id)
        if aso_node is None:
            return None
        oem_node: Optional[OrbitEphemerisMessage]
        oem_node = aso_node.ephemeris_messages \
                           .order_by('-stop_time') \
                           .first_or_none()
        return oem_node


class OrbitEphemerisMessage(BaseAccess):
    """A `neomodel` model representing an orbit ephemeris message. """
    ephemeris_lines = JSONProperty()
    ccsds_oem_vers = StringProperty()
    creation_date = StringProperty()
    originator = StringProperty()
    object_name = StringProperty()
    object_id = StringProperty()
    center_name = StringProperty()
    ref_frame = StringProperty()
    time_system = StringProperty()
    start_time = StringProperty()
    stop_time = StringProperty()

    in_cos_object = RelationshipTo('COSObject', 'stored_in')


class Compliance(BaseAccess):
    """A `neomodel` model representing whether an ASO is compliant with the
    UN's registration requirements. """
    is_compliant = BooleanProperty(required=True)
