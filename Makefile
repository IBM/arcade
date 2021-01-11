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


.PHONY : build clean test type_check run

build:
	docker build -t arcade:latest .

clean:
	docker rmi -f arcade:latest

type_check: build
	docker run --rm arcade:latest mypy --strict /arcade

test: build type_check
	docker run --rm arcade:latest python3 -m pytest --cache-clear --flake8

run: build
	docker run --rm \
	-p 8000:8000 \
	-e DEV=true \
	-v $(shell pwd):/arcade \
	arcade:latest uvicorn arcade.api:app --host 0.0.0.0

jupyter: build
	docker run --rm \
	-p 8888:8888 \
	-v $(shell pwd):/arcade \
	arcade:latest jupyter notebook --allow-root --ip 0.0.0.0
