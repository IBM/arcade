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

from typing import Optional, TypeVar, Type
from neomodel import (StringProperty, EmailProperty,  # type: ignore
                      JSONProperty, BooleanProperty)
from neomodel import StructuredNode, RelationshipTo, RelationshipFrom

NodeType = TypeVar('NodeType', bound='StructuredNode')


class FindMixin:
    @classmethod
    def find(cls: Type[NodeType], **kwargs: str) -> Optional[NodeType]:
        node: Optional[NodeType] = cls.nodes.first_or_none(**kwargs)
        return node


class User(StructuredNode):  # type: ignore
    email = EmailProperty(unique_index=True, required=True)
    pwd_hash = StringProperty(required=True)
    pwd_salt = StringProperty(required=True)
    api_key = StringProperty(unique_index=True, required=True)

    collections = RelationshipTo('Collection', 'has_access')

    def post_create(self) -> None:
        self._add_public_data_sources()

    def _add_public_data_sources(self) -> None:
        public_collections = Collection.nodes.filter(public=True)
        for pc in public_collections:
            self.collections.connect(pc)


class Collection(StructuredNode):  # type: ignore
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
    cospar_id = StringProperty(unique_index=True, required=True)
    name = StringProperty()

    ephemeris_messages = RelationshipTo('OrbitEphemerisMessage', 'has_oem')

    @classmethod
    def get_latest_oem(cls, aso_id: str) -> Optional[OrbitEphemerisMessage]:
        aso_node = cls.find(aso_id=aso_id)
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

    from_collection = RelationshipTo('Collection', 'from_collection')
    in_cos_object = RelationshipTo('COSObject', 'stored_in')
