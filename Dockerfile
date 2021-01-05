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


FROM python:3.8-slim-buster

RUN mkdir -p /usr/share/man/man1 /usr/share/man/man2
RUN apt-get update -qq && \
        apt-get install -yq --no-install-suggests --no-install-recommends \
        openjdk-11-jre \
        git

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /arcade/requirements.txt
RUN chmod -R g=u /arcade
WORKDIR /arcade

RUN pip install --upgrade pip wheel
RUN pip install -r requirements.txt

COPY . /arcade
