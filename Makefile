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


.PHONY : build clean test type_check

build:
	docker build -t arcade:latest .

clean:
	docker rmi -f arcade:latest

type_check: build
	docker run arcade mypy --strict /app

test: build type_check
	docker run arcade python3 -m pytest --cache-clear --flake8
