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


<a id="org6437ebb"></a>

# Demo Client Applications


## Conjunction Search

The [conjunction search demo](https://spaceorbits.net) of the [space situational awareness](https://github.com/ibm/spacetech-ssa) project now uses the `/ephemeris` ARCADE API endpoint to gather the up-to-date orbit state vector data and then determine the nearest conjunctions of each satellite. ![img](docs/conj.png)


## Observatory Light Pollution

[Daniel Kucharski](https://www.oden.utexas.edu/people/1610/) of the University of Texas at Austin has developed a [C++ library](https://github.com/danielkucharski/SatLightPollution) for determining how much light pollution a terrestrial based astronomical observatory will experience over a given time period due to ASOs passing overhead. [This demo](https://slp.spacetech-ibm.com) utilizes ARCADE's `/interpolate` endpoint and the satellite light pollution library to show the brightness of ASOs currently above the New Mexico skys. Redder objects are brighter while bluer objects are more dim. ![img](docs/slp.png)


## UNOSSA Compliance

In [this demo](https://astriagraph.spacetech-ibm.com) we combine [ASTRIAGraph](http://astria.tacc.utexas.edu/AstriaGraph/) and the `\compliance` ARCADE endpoint to show what ASOs are in compliance with UNOSSA's registration requirements. ![img](docs/astriagraph.png)


# Development and Extending the ARCADE API

The ARCADE PoC is developed using Python 3.8 with the [FastAPI](https://fastapi.tiangolo.com) framework. We utilize [docker](https://www.docker.com) to develop, test, and deploy the API. The PoC API and all of the demos mentioned [above](#org6437ebb) are deployed on [Red Hat's OpenShift platform](https://www.openshift.com) on [IBM Cloud](https://www.ibm.com/cloud). A [makefile](Makefile) is provided to run most of the common development tasks like:

| Command           | Description                                                                     |
|----------------- |------------------------------------------------------------------------------- |
| `make build`      | Builds a docker image                                                           |
| `make clean`      | Removes all built docker images                                                 |
| `make type_check` | Uses [mypy](https://mypy.readthedocs.io/en/stable/) to type check the code base |
| `make test`       | Runs the test suite                                                             |
| `make run`        | Runs the API locally at <http://localhost:8000>                                 |

The ARCADE project is meant to be extended by allowing community members to add new data sources, algorithms, and API endpoints.


## Adding Data


### Graph Database

![img](docs/arcade_graph2.png)


### Data Importers


## Adding New Algorithms and API Models


## Adding API Endpoints


# Contributing

We very much encourage anyone and everyone to join and contribute to this project. Please see the [contributing file](file:///Users/colin/projects/arcade/CONTRIBUTING.md) for more details.


# License

ARCADE is licensed under the Apache 2.0 license. Full license text is available at [LICENSE](file:///Users/colin/projects/arcade/LICENSE).
