[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![Project Maintenance][maintenance-shield]][user_profile]
[![License][license-shield]][license]
[![pre-commit][pre-commit-shield]][pre-commit]
[![black][black-shield]][black]
[![calver][calver-shield]][calver]
[![hacs][hacsbadge]][hacs]

This is the unofficial Hilo integration. [Hilo](https://www.hiloenergie.com/en-ca/) is a smart home platform developed
by an [Hydro Quebec](https://www.hydroquebec.com/hilo/en/) subsidiary.
This integration has no direct tie with Hilo or Hydro Quebec. This is a community initiative. Please don't contact
Hilo or Hydro-Quebec with issues with this Home Assistant integration, you can open an issue in the github repository
instead.

If you want to help with the development of this integration, you can always submit a feedback form from the Hilo
application and requesting that they open their API publicly and that they provide a testing environment to the
developers.


**This component will set up the following platforms.**

| Platform        | Description                                                                 |
| --------------- | --------------------------------------------------------------------------- |
| `light`         | Control light switches and dimmers                                          |
| `sensor`        | Status of various devices, Hilo challenges, gateway and energy cost sensors |
| `climate`       | Control the Hilo thermostat                                                 |
| `utility_meter` | Various meters will be created to integrate with the Energy Dashboard       |
| `energy`        | Energy dashboard will be automatically configured with all devices          |

{% if not installed %}

## Installation

1. Click install.
1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Hilo".

{% endif %}

## Configuration

The configuration is done in the UI. When you add the integration, you will be prompted with your
Hilo username and password. After this, you will be prompted with assigning a room for each one of
your devices. Finally, if you want to enable the automatic generation of the energy sensors, you
need to make sure that the `utility_meter` platform is loaded in your `configuration.yaml` file from
home assistant. You simply need to add a line like this in your `configuration.yaml`:

```
utility_meter:
```

After this, you can click on `Configure` in the integration UI and check the `Generate energy meters`
box, followed by a home assistant restart.

<!---->

## Credits

Credits to to [Francis Poisson](https://github.com/francispoisson/) who's the original author of this integration.

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[commits-shield]: https://img.shields.io/github/commit-activity/y/dvd-dev/hilo.svg?style=for-the-badge
[commits]: https://github.com/dvd-dev/hilo/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license]: https://github.com/dvd-dev/hilo/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/dvd-dev/hilo.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40dvd-dev-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/dvd-dev/hilo.svg?style=for-the-badge
[releases]: https://github.com/dvd-dev/hilo/releases
[user_profile]: https://github.com/dvd-dev
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
[pre-commit]: https://github.com/pre-commit/pre-commit
[calver-shield]: https://img.shields.io/badge/calver-YYYY.MM.Micro-22bfda.svg
[calver]: http://calver.org/
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg
[black]: https://github.com/psf/black
