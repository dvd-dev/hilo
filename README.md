[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Project Maintenance][maintenance-shield]][user_profile]
[![License][license-shield]][license]
[![pre-commit][pre-commit-shield]][pre-commit]
[![black][black-shield]][black]
[![calver][calver-shield]][calver]
[![lgtm-alert][lgtm-alert-shield]][lgtm-alert]
[![lgtm-grade][lgtm-grade-shield]][lgtm-grade]
[![discord][discord-shield]][discord]


**BETA** This is a beta release. There will be some bugs, issues, etc. Please bear with us and open issues in the repo.

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
- ~~Write a separate library for the hilo api mapping~~ Now available [here](https://github.com/dvd-dev/python-hilo)
- Translate everything in French `#tokebakissite`

## Installation

### Manual

Copy the `custom_components/hilo` directory from the latest release to your `custom_components` directory.

### HACS

Follow standard HACS procedure to install.

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

### Other configuration

Other options are available under the `Configure` button in Home Assistant:

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

If you have any kind of python/home-assistant experience and want to contribute to the code, feel free to submit a merge request.


### Collaborators

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
[lgtm-alert]: https://lgtm.com/projects/g/dvd-dev/hilo/alerts/
[lgtm-alert-shield]: https://img.shields.io/lgtm/alerts/g/dvd-dev/hilo.svg?logo=lgtm&style=for-the-badge
[lgtm-grade]: https://lgtm.com/projects/g/dvd-dev/hilo/context:python
[lgtm-grade-shield]: https://img.shields.io/lgtm/grade/python/g/dvd-dev/hilo.svg?logo=lgtm&style=for-the-badge
[discord-shield]: https://img.shields.io/badge/discord-Chat-green?logo=discord&style=for-the-badge
[discord]: https://discord.gg/MD5ydRJxpc
