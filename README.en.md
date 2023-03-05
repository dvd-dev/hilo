[![Français][Françaisshield]][Français]
[![English][Englishshield]][English]

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Project Maintenance][maintenance-shield]][user_profile]
[![License][license-shield]][license]
[![pre-commit][pre-commit-shield]][pre-commit]
[![black][black-shield]][black]
[![calver][calver-shield]][calver]
[![discord][discord-shield]][discord]


**BETA** 

This is a beta release. There will be some bugs, issues, etc. Please bear with us and open issues in the repo.

# Hilo
[Hilo](https://www.hydroquebec.com/hilo/en/) integration for Home Assistant

## Introduction

This is the unofficial HACS Hilo integration for Home Assistant. [Hilo](https://www.hiloenergie.com/en-ca/) is a smart home platform developed
by an [Hydro Quebec](https://www.hydroquebec.com/hilo/en/) subsidiary.
This integration has no direct tie with Hilo or Hydro Quebec. This is a community initiative. Please don't contact
Hilo or Hydro-Quebec with issues with this Home Assistant integration, you can open an issue in the github repository
instead.

If you want to help with the development of this integration, you can always submit a feedback form from the Hilo
application and requesting that they open their API publicly and that they provide a testing environment to the
developers.

### Shout out

Big shout out to [Francis Poisson](https://github.com/francispoisson/) who's the original author of this integration. Without the work
he put into this integration, I would probably have never even considered Hilo.

I decided to move the integration here because of the latest updates from Hilo broke the original one and I took the time to completely
rewrite it. Hilo is now pushing device readings via websocket from SignalR.

### Features
- Support for switches and dimmers as light devices
- Get current and set target temperature of thermostat
- Get energy usage of pretty much each devices
- Generates energy meters and sensors
- Sensor for Hilo Events (challenges)
- Sensor for Hilo Gateway
- **NEW**: Now configuration is done via the UI
- **NEW**: Updates are now closer to realtime

### To Do:
- Add functionalities for other devices
- unit and functional tests
- [Adding type hints to the code](https://developers.home-assistant.io/docs/development_typing/)
- Now available [here](https://github.com/dvd-dev/python-hilo)
- Map send energy meters automatically to enegery dashboard


## Installation

### Step 1: Download files

#### Option 1: Via HACS

Make sure you have [HACS](https://hacs.xyz/docs/setup/download/) installed.
Under HACS, click the '+ EXPLORE & DOWNLOAD REPOSITORIES' button on the bottom of the page, serch for "Hilo", choose it, and click _download_ in HACS.

#### Option 2: Manual

Download and copy the `custom_components/hilo` directory from the [latest release](https://github.com/dvd-dev/hilo/releases/latest) to your `custom_components` directory in HA.

### Step 2: Add integration to HA (<--- this is a step that a lot of people forget)

In HA, go to Settings > Devices & Services > Integrations.
In the bottom right corner, click the '+ ADD INTEGRATION' button.

If the component is properly installed, you should be able to find the 'Hilo integration' in the list. You might need to clear you browser cache for the integration to show up.

## Configuration

The configuration is done in the UI. When you add the integration, you will be prompted with your
Hilo username and password. After this, you will be prompted with assigning a room for each one of
your devices.

### Energy meters

Energy meters are a new feature of this integration. We used to manually generate them with template sensors and automation
but they now have been fully integrated into the Hilo integration.

#### Warning

When enabling Hilo generated energy meters, it's recommended to remove the manually generated ones to have the most accurate
statistics, otherwise we might end up with duplicated data.

This wasn't tested with already active data and energy entities (ie: Battery, Gaz, Solar, or even other individual devices).
It's possible that enabling this will break or delete these original sensors. We can't be held responsible for any data loss
service downtime, or any kind as it's described in the license.

If you're facing an issue and you want to collaborate, please enable `debug` log level for this integration and provide a copy
of the `home-assistant.log` file. Details on how to enable `debug` are below.

#### Procedure

If you want to enable the automatic generation of the energy sensors, follow these steps:

* Make sure that the `utility_meter` platform is loaded in your `configuration.yaml` file from
home assistant. You simply need to add a line like this in your `configuration.yaml`:

    ```
    utility_meter:
    ```

* Click `Configure` in the integration UI and check the `Generate energy meters` box.

* Restart home assistant and wait 5 minutes until you see the `sensor.hilo_energy_total_low` entity getting created and populated
  with data:
  * The `status` should be in `collecting`
  * The `state` should be a number higher than 0.

* All generated entities and sensors will be prefixed with `hilo_energy_` or `hilo_rate_`.

* If you see the following error in your logs, this is a bug in Home Assistant and it's because the power meter in question has 0 w/h
  usage so far. This will disappear once usage has been calculated. There's a PR upstream [here](https://github.com/home-assistant/core/pull/60678) to address this.

    ```
    2021-11-29 22:03:46 ERROR (MainThread) [homeassistant] Error doing job: Task exception was never retrieved
    Traceback (most recent call last):
    [...]
    ValueError: could not convert string to float: 'None'
    ```
Once created, energy meters will then have to be added manually to the energy dashboard.


### Other configuration

Other options are available under the `Configure` button in Home Assistant:

- `Generate energy meters`: Checkbox

  Automatically generate energy meters, see procedure above for proper setup

- `Generate only total meters for each devices`: Checkbox

  Calculate only energy total without splitting between low cost and high cost

- `Also log request data and websocket messages (requires debug log level on both the integration and pyhilo)`: Checkbox

  Allows higher logging level for developers/debugging

- `Lock climate entities during Hilo challenges, preventing any changes when a challenge is in progress.`

  Prevents modifying temperature setpoints during Hilo Challenges

- `Track unknown power sources in a separate energy sensor. This is a round approximation calculated when we get a reading from the Smart Energy Meter.`: Checkbox

  All energy sources other than Hilo hardware are lumped into a single sensor. Uses the reading from the home's smart meter.

- `hq_plan_name`: String

  Define the Hydro Quebec rate plan name.
  Only 2 values are supported at this time:
  - `rate d`
  - `flex d`

- `scan_interval`: Integer

  Number of seconds between each device update. Defaults to 60 and it's not recommended to go below 30 as it might
  result in a suspension from Hilo.

## Lovelace sample integration and automation example

You can find multiple examples and ideas for lovelace dashboard, cards and automation here [in the wiki of the project](https://github.com/dvd-dev/hilo/wiki/Utilisation)


## References

As stated above, this is an unofficial integration. Hilo is not supporting direct API calls and might obfuscate the service or
prevent us from using it.

For now, these are the swagger links we've found:
* https://wapphqcdev01-automation.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-notification.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-clientele.azurewebsites.net/swagger/index.html

## FAQ

You can find the FAQ in the wiki of the project: https://github.com/dvd-dev/hilo/wiki/FAQ

## Contributing

Reporting any kind of issue is a good way of contributing to the project and it's available to anyone.

If you face any kind of problem or weird behavior, please submit an issue and ideal, attach debug logs.

To enable debug log level, you need to add this to your `configuration.yaml` file:
```
logger:
  default: info
  logs:
     custom_components.hilo: debug
     pyhilo: debug
```

If you have any kind of python/home-assistant experience and want to contribute to the code, feel free to submit a pull request.

### Submitting a Pull Request

- First you need to `fork` the repository into your own userspace.
- And then, you can `clone` it on your computer.
- To maintain some kind of tidyness and standard in the code, we have some linters and validators that need to be executed via `pre-commit` hooks:
```
pre-commit install --install-hooks
```
- You can now proceed with whatever code change you want.
- Once you're done with the code change, you can `stage` the files for a `commit`:
```
git add path/to/file
```
- And you can create a `commit`:
```
git commit -m "I changed this because blabla"
```
- Finally, you can `push` the change on your upstream repository:
```
git push
```
- At this point, if you visit the [upstream repository](https://github.com/dvd-dev/hilo), Github should prompt you to create a Pull Request (aka PR). Just follow the instructions.

### Initial collaborators

* [Francis Poisson](https://github.com/francispoisson/)
* [David Vallee Delisle](https://github.com/valleedelisle/)


---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[commits-shield]: https://img.shields.io/github/commit-activity/y/dvd-dev/hilo.svg?style=for-the-badge
[commits]: https://github.com/dvd-dev/hilo/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[license]: https://github.com/dvd-dev/hilo/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/dvd-dev/hilo.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40dvd--dev-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/dvd-dev/hilo.svg?style=for-the-badge
[releases]: https://github.com/dvd-dev/hilo/releases
[user_profile]: https://github.com/dvd-dev
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[calver-shield]: https://img.shields.io/badge/calver-YYYY.MM.Micro-22bfda.svg?style=for-the-badge
[calver]: http://calver.org/
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[black]: https://github.com/psf/black
[discord-shield]: https://img.shields.io/badge/discord-Chat-green?logo=discord&style=for-the-badge
[discord]: https://discord.gg/MD5ydRJxpc
[Englishshield]: https://img.shields.io/badge/en-English-red?style=for-the-badge
[English]: https://github.com/dvd-dev/hilo/blob/main/README.md
[Françaisshield]: https://img.shields.io/badge/fr-Français-blue?style=for-the-badge
[Français]: https://github.com/dvd-dev/hilo/blob/main/README.md
