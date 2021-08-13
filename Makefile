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


.PHONY : build clean test type_check run push deploy

build:
	docker build -t arcade:latest .

clean:
	docker rmi -f arcade:latest
	find . -type f -name ‘*.pyc’ -delete

type_check: build
	docker run --rm arcade:latest mypy --strict --implicit-reexport --allow-untyped-decorators /arcade

test: build type_check
	docker run --rm arcade:latest python3 -m pytest --cache-clear --flake8

run: docker compose up

push: build
	docker tag arcade:latest us.icr.io/astriagraph/arcade
	docker push us.icr.io/astriagraph/arcade

deploy: push
	oc project arcade
	oc apply -f deploy/deploy_app.yaml
	oc delete pods --selector app=arcade
