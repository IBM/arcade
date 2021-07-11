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
        node: NodeType = cls.nodes.first_or_none(**kwargs)
        return node


class FastAPIUserDBAdapter(BaseUserDatabase[UD]):
    def __init__(self, user_db_model: Type[UD]):
        super().__init__(user_db_model)

    @aioify
    def get(self, uid: UUID4) -> Optional[UD]:
        user = User.find_one(uid=str(uid))
        if user:
            return self.user_db_model(**user.to_dict())
        else:
            return None

    @aioify
    def get_by_email(self, email: str) -> Optional[UD]:
        user = User.find_one(email=email)
        if user:
            return self.user_db_model(**user.to_dict())
        else:
            return None

    @aioify
    def create(self, user: UD) -> UD:
        user_dict = user.dict()
        user_dict['uid'] = user_dict.pop('id')
        User(**user_dict).save()
        return user

    @aioify
    def update(self, user: UD) -> UD:
        user = User.create_or_update(user.dict())
        return user

    @aioify
    def delete(self, user: UD) -> None:
        user_node = User.find_one(uid=str(user.id))
        if user_node:
            user_node.delete()


class AccessRel(StructuredRel):  # type: ignore
    time = DateTimeProperty(default_now=True)
    endpoint = StringProperty(required=True)


class BaseAccess(StructuredNode):  # type: ignore
    from_data_source = RelationshipTo('DataSource', 'from_data_source')
    accessed_by = RelationshipFrom('User', 'accessed', model=AccessRel)


class User(StructuredNode, FindMixin):  # type: ignore
    uid = UniqueIdProperty()
    email = EmailProperty(unique_index=True, required=True)
    hashed_password = StringProperty(required=True)
    is_active = BooleanProperty()
    is_verified = BooleanProperty()
    is_superuser = BooleanProperty()

    data_sources = RelationshipTo('DataSource', 'has_access')
    accessed_oem = RelationshipTo('OrbitEphemerisMessage',
                                  'accessed',
                                  model=AccessRel)
    accessed_compliance = RelationshipTo('Compliance',
                                         'accessed',
                                         model=AccessRel)

    def post_create(self) -> None:
        self._add_public_data_sources()

    def _add_public_data_sources(self) -> None:
        public_data_sources = DataSource.nodes.filter(public=True)
        for pds in public_data_sources:
            self.data_sources.connect(pds)

    def to_dict(self) -> Dict[str, Union[str, bool]]:
        d = self.__dict__.copy()
        d['id'] = d.pop('uid')
        return d

    def can_access(self, node: BaseAccess) -> bool:
        node_source = node.from_data_source.all()[0]
        user_sources = self.data_sources.all()
        return node_source in user_sources


class DataSource(StructuredNode):  # type: ignore
    name = StringProperty(unique_index=True, required=True)
    public = BooleanProperty()


class COSBucket(StructuredNode):  # type: ignore
    name = StringProperty(unique_index=True, required=True)

    objects = RelationshipFrom('COSObject', 'in_bucket')


class COSObject(StructuredNode):  # type: ignore
    name = StringProperty(unique_index=True, required=True)
    imported = BooleanProperty()
    bucket = RelationshipTo('COSBucket', 'in_bucket')


class SpaceObject(StructuredNode, FindMixin):  # type: ignore
    aso_id = StringProperty(unique_index=True, required=True)
    norad_id = StringProperty(unique_index=True, required=True)
    cospar_id = StringProperty()
    name = StringProperty()

    ephemeris_messages = RelationshipTo('OrbitEphemerisMessage', 'has_oem')
    compliance = RelationshipTo('Compliance', 'has_compliance')

    @classmethod
    def get_latest_oem(cls, aso_id: str) -> Optional[OrbitEphemerisMessage]:
        aso_node = cls.find_one(aso_id=aso_id)
        if aso_node is None:
            return None
        oem_node: Optional[OrbitEphemerisMessage]
        oem_node = aso_node.ephemeris_messages \
                           .order_by('-stop_time') \
                           .first_or_none()
        return oem_node


class OrbitEphemerisMessage(StructuredNode):  # type: ignore
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
    from_data_source = RelationshipTo('DataSource', 'from_data_source')
    accessed_by = RelationshipFrom('User', 'accessed', model=AccessRel)


class Compliance(StructuredNode):  # type: ignore
    is_compliant = BooleanProperty(required=True)
    from_data_source = RelationshipTo('DataSource', 'from_data_source')
    accessed_by = RelationshipFrom('User', 'accessed', model=AccessRel)
