# ARCADE

The Advanced Research Collaboration and Application Development Environment (ARCADE) is a collaboration project between the [ASTRIA Research Group](https://sites.utexas.edu/moriba/) at the University of Texas at Austin, the IBM Space Tech team, and other partners. The goal of this repository is to provide a unified and coherent API for accessing, analyzing, and extending a diverse set of derived data points concerning an anthropogenic space object (ASO). Note: this repository currently represents a small proof of concept and is in a very alpha state of development, so APIs (internal and external) may change greatly.


## API Accounts

Accessing the ARCADE API requires an account and registering for one
can be done through the API like so:

```bash
curl -X 'POST' \
  'https://arcade.spacetech-ibm.com/auth/register' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "<EMAIL ADDRESS>",
  "password": "<PASSWORD>"
}'
```

The ARCADE API endpoints are secured via [JSON Web Tokens (JWT)](https://jwt.io).
```bash
curl -X 'POST' \
  'https://arcade.spacetech-ibm.com/auth/jwt/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=<EMAIL ADDRESS>&password=<PASSWORD>'
```
which results in the response
```json
{
  "access_token": "<JSON WEB TOKEN>",
  "token_type": "bearer"
}
```

## API

Interactive [swagger](https://swagger.io/tools/swagger-ui/) documentation for the API where you can try it out in a web browser is available [here](https://arcade.spacetech-ibm.com/docs).  The currently provided endpoints that you can programmatically test via the base URI https://arcade.spacetech-ibm.com are:

| Endpoint     | Description                                                                                                                                             |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| /asos        | Returns basic information on all the ASOs that ARCADE knows about like its name and various identifiers                                                 |
| /aso         | Returns the basic information for a single ASO                                                                                                          |
| /ephemeris   | Provides the most up-to-date ephemeris data for an ASO                                                                                                  |
| /interpolate | Uses UT's [`orbdetpy` library](https://github.com/ut-astria/orbdetpy) to interpolate the ephemeris data for the ASO to the specified temporal frequency |
| /compliance  | Reports whether the ASO is compliant with the United Nation's requirements for object registration                                                      |


## Architecture

![img](arcade_arch.png) The ARCADE platform ingests data from multiple raw and preprocessed sources including telescopes, radar arrays, and TLE data from different providers and fuses it into a coherent view of each ASO. This data fusion is done in [ASTRIAGraph](https://sites.utexas.edu/moriba/astriagraph/) with the data being stored in the graph database or IBM's [cloud object storage (COS)](https://www.ibm.com/products/cloud-object-storage) depending on the data type. A RESTful API is then used to provide access to this rich data to developers and client applications.

# Demo Client Applications


## Conjunction Search

The [conjunction search demo](https://spaceorbits.net) of the [space situational awareness](https://github.com/ibm/spacetech-ssa) project now uses the `/ephemeris` ARCADE API endpoint to gather the up-to-date orbit state vector data and then determine the nearest conjunctions of each satellite. ![img](conj.png)


## Observatory Light Pollution

[Daniel Kucharski](https://www.oden.utexas.edu/people/1610/) of the University of Texas at Austin has developed a [C++ library](https://github.com/danielkucharski/SatLightPollution) for determining how much light pollution a terrestrial based astronomical observatory will experience over a given time period due to ASOs passing overhead. [This demo](https://slp.spacetech-ibm.com) utilizes ARCADE's `/interpolate` endpoint and the satellite light pollution library to show the brightness of ASOs currently above the New Mexico skys. Redder objects are brighter while bluer objects are more dim. ![img](slp.png)


## UNOSSA Compliance

In [this demo](https://astriagraph.spacetech-ibm.com) we combine [ASTRIAGraph](http://astria.tacc.utexas.edu/AstriaGraph/) and the `\compliance` ARCADE endpoint to show what ASOs are in compliance with UNOSSA's registration requirements. ![img](astriagraph.png)

# Contributing

We very much encourage anyone and everyone to join and contribute to this project. Please see the [contributing file](file:///Users/colin/projects/arcade/CONTRIBUTING.md) for more details.

