# ARCADE

The Advanced Research Collaboration and Application Development Environment (ARCADE) is a collaboration project between the [ASTRIA Research Group](https://sites.utexas.edu/moriba/) at the University of Texas at Austin, the IBM Space Tech team, and other partners. The goal of this repository is to provide a unified and coherent API for accessing, analyzing, and extending a diverse set of derived data points concerning an anthropogenic space object (ASO). Note: this repository currently represents a small proof of concept and is in a very alpha state of development, so APIs (internal and external) may change greatly.


# System Architecture

![img](docs/arcade_arch.png)

The ARCADE platform ingests data from multiple raw and preprocessed sources including telescopes, radar arrays, and TLE data from different providers and fuses it into a coherent view of each ASO. This data fusion is done in [ASTRIAGraph](https://sites.utexas.edu/moriba/astriagraph/) with the data being stored in the graph database or IBM's [cloud object storage (COS)](https://www.ibm.com/products/cloud-object-storage) depending on the data type. A RESTful API is then used to provide access to this rich data to developers and client applications.


# API

Interactive documentation for the API where you can try it out in a web browser is available [here](https://arcade.spacetech-ibm.com/docs). The currently provided endpoints that you can programmatically test via the base URI <https://arcade.spacetech-ibm.com> are:

| Endpoint     | Description                                                                                                                                             |
|------------ |------------------------------------------------------------------------------------------------------------------------------------------------------- |
| /asos        | Returns basic information on all the ASOs that ARCADE knows about like its name and various identifiers                                                 |
| /aso         | Returns the basic information for a single ASO                                                                                                          |
| /ephemeris   | Provides the most up-to-date ephemeris data for an ASO                                                                                                  |
| /interpolate | Uses UT's [`orbdetpy` library](https://github.com/ut-astria/orbdetpy) to interpolate the ephemeris data for the ASO to the specified temporal frequency |
| /compliance  | Returns whether or not the ASO is compliant in registering with UNOSSA                                                                                  |


<a id="org01e58d2"></a>

# Demo Client Applications


## Conjunction Search

The [conjunction search demo](https://spaceorbits.net) of the [space situational awareness](https://github.com/ibm/spacetech-ssa) project now uses the `/ephemeris` ARCADE API endpoint to gather the up-to-date orbit state vector data and then determine the nearest conjunctions of each satellite. ![img](docs/conj.png)


## Observatory Light Pollution

[Daniel Kucharski](https://www.oden.utexas.edu/people/1610/) of the University of Texas at Austin has developed a [C++ library](https://github.com/danielkucharski/SatLightPollution) for determining how much light pollution a terrestrial based astronomical observatory will experience over a given time period due to ASOs passing overhead. [This demo](https://slp.spacetech-ibm.com) utilizes ARCADE's `/interpolate` endpoint and the satellite light pollution library to show the brightness of ASOs currently above the New Mexico skys. Redder objects are brighter while bluer objects are more dim. ![img](docs/slp.png)


## UNOSSA Compliance

In [this demo](https://astriagraph.spacetech-ibm.com) we combine [ASTRIAGraph](http://astria.tacc.utexas.edu/AstriaGraph/) and the `\compliance` ARCADE endpoint to show what ASOs are in compliance with UNOSSA's registration requirements. ![img](docs/astriagraph.png)


# Development and Extending the ARCADE API

The ARCADE PoC is developed using Python 3.8 with the [FastAPI](https://fastapi.tiangolo.com) framework. We utilize [docker](https://www.docker.com) and [docker-compose](https://docs.docker.com/compose/) to develop, test, and deploy the API. The PoC API and all of the demos mentioned [above](#org82ad767) are deployed on [Red Hat's OpenShift platform](https://www.openshift.com) on [IBM Cloud](https://www.ibm.com/cloud). A [makefile](Makefile) is provided to run most of the common development tasks like:

| Command           | Description                                                                     |
|----------------- |------------------------------------------------------------------------------- |
| `make build`      | Builds a docker image                                                           |
| `make clean`      | Removes all built docker images                                                 |
| `make type_check` | Uses [mypy](https://mypy.readthedocs.io/en/stable/) to type check the code base |
| `make test`       | Runs the test suite                                                             |
| `make run`        | Runs the API locally at <http://localhost:8080>                                 |

The ARCADE project is meant to be extended by allowing community members to add new data sources, algorithms, and API endpoints.


## Adding Data


### Graph Database

The ARCADE PoC utilizes the [neo4j](https://neo4j.com) graph database as the operational data store. The current schema has the following entity-relationship diagram.

![img](docs/arcade_graph2.png)

The `SpaceObject` node type is used to store data about an ASO that does not frequently change like various catalog IDs and the object's name. When adding new data nodes, they should be linked from the specific `SpaceObject` node. The `DataSource`, `COSBucket`, and `COSObject` node types are used to track the provenance of imported data into the graph. The `User` node type is used to store information used in the authentication and authorization process. The `has_access` relationship is used to determine if a `User` has the permission to access the data provided by the `DataSource`. If a `DataSource` node has the `public` property set to `True` then every `User` node in the database will have access to all data provided by the `DataSource`. The `accessed` relationship is used to keep track of when and through what API endpoint the `User` accessed a data node. We use the [neomodel](https://neomodel.readthedocs.io/en/latest/) object graph mapper (OGM) in the [`graph`](arcade/models/graph.py) module to define the properties and relationships between the various nodes in the graph. Node type models that provide data for a `SpaceObject` from a `DataSource` should inherit from the `BaseAccess` class, which adds the necessary relationships for managing `User` access to the data. The `FindMixin` class provides useful functions for querying the various node types in the graph.


### Data Importers

The [`importers`](arcade/importers/) package is where scripts are kept that import data into the graph. An `importer` class should implement a `run` method that takes no arguments. The `run` function should be idempotent with regards to the state of the graph and should keep track of what data needs to be imported. See the [UT OEM](arcade/importers/cos_oem/ut_oem.py), [Starlink OEM](arcade/importers/cos_oem/starlink_oem.py), and [UN Compliance](arcade/importers/un_compliance.py) importers as examples.


## Adding New Algorithms and API Models

The [API models](arcade/models/api.py) module implements [pydantic](https://pydantic-docs.helpmanual.io) models that are served by the API. The API models are used to validate that the data is valid and the model's [Config](https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances) is used to make turning a `graph` model into an `api` model seamless. The API model is the place to implement new algorithms atop of existing data models. See the `interpolate` method of the `OrbitEphemerisMessage` class as an example.


## Adding API Endpoints

The [FastAPI](https://fastapi.tiangolo.com) endpoints can be found in the [API](arcade/api.py) module. When exposing data from a `DataSource`, the endpoint should check that the `User` has the appropriate permissions using the `can_access` method on the `User` instance, and then add an `accessed` relationship in the graph containing the endpoint used. See the `/ephemeris`, `/interpolate`, and `/compliance` endpoints as examples.


# Contributing

We very much encourage anyone and everyone to join and contribute to this project. Please see the [contributing file](file:///Users/colin/projects/arcade/CONTRIBUTING.md) for more details.


# License

ARCADE is licensed under the Apache 2.0 license. Full license text is available at [LICENSE](file:///Users/colin/projects/arcade/LICENSE).
