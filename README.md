[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)


**BETA** This is a beta release. There will be some bugs, issues, etc. Please bear with us and open issues in the repo.

# Hilo
[Hilo](https://www.hydroquebec.com/hilo/en/) integration for Home Assistant

## Introduction

This is a custom component to allow control of Hilo devices from Home Assistant. This is an unofficial integration and unsupported
by Hilo.

We are not employees of, or paid by, Hilo. We can't be held responsible if your account is getting suspended because of the use of
this integration. Hilo might change their API any time and this might break this integration.

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

Just add the integration in the Integrations GUI.

If you want to use the energy meters, make sure you have a `utility_meter` section in your `configuration.yaml` file, even if it's empty.

### Advanced configuration

Some options are available under the `Configure` button in Home Assistant:

- `generate_energy_meters`: Boolean (beta)
  Will generate all the entities and sensors required to feed the `Energy` dashboard.
  For details, see the [note below](#energy-meters).

- `hq_plan_name`: String
  Define the Hydro Quebec rate plan name.
  Only 2 values are supported at this time:
  - `rate d`
  - `flex d`

- `scan_interval`: Integer
  Number of seconds between each device update. Defaults to 60 and it's not recommended to go below 30 as it might
  result in a suspension from Hilo.

## Energy meters
Energy meters are a new feature of this integration. We used to manually generate them with template sensors and automation
but they now have been fully integrated into the Hilo integration.

All generated entities and sensors will be prefixed with `hilo_energy_` or `hilo_rate_`.

### How to enable them

* If you never configured any utility meter, you will need to add an empty `utility_meter` block in your `configuration.yaml`.
  The reason why we do this is because there's no official API to integrate the meters.

* Restart home assistant and wait 5 minutes until you see the `sensor.hilo_energy_total_low` entity gettin created and populated
  with data:
  * The `status` should be in `collecting`
  * The `state` should be a number higher than 0.

* If you see the following error in your logs, this is a bug in Home Assist and it's because the power meter in question has 0 w/h
  usage so far. This will disappear once usage has been calculated. There's a PR upstream [here](https://github.com/home-assistant/core/pull/60678) to address this.

    ```
    2021-11-29 22:03:46 ERROR (MainThread) [homeassistant] Error doing job: Task exception was never retrieved
    Traceback (most recent call last):
    [...]
    ValueError: could not convert string to float: 'None'
    ```

### Lovelace sample integration

Here's an example on how to add the energy data to Lovelace:
```
      - type: vertical-stack
        cards:
          - type: horizontal-stack
            cards:
              - type: entity
                entity: binary_sensor.defi_hilo
                icon: mdi:fire
              - type: entity
                entity: sensor.smartenergymeter
                name: Hydro
                icon: mdi:speedometer
              - type: entity
                entity: sensor.hilo_rate_current
                name: Cout Actuel
          - type: energy-date-selection
          - type: energy-sources-table
          - type: energy-usage-graph
          - type: energy-distribution
            link_dashboard: true
```


### Warning

When enabling Hilo generated energy meters, it's recommended to remove the manually generated ones to have the most accurate
statistics, otherwise we might end up with duplicate data.

This wasn't tested with already active data and energy entities (ie: Battery, Gaz, Solar, or even other individual devices).
It's possible that enabling this will break or delete these original sensors. We can't be held responsible for any data loss
service downtime, or any kind as it's described in the license.

If you're facing an issue and you want to collaborate, please enable `debug` log level for this integration and provide a copy
of the `home-assistant.log` file. Details on how to enable `debug` are below.

## References

As stated above, this is an unofficial integration. Hilo is not supporting direct API calls and might obfuscate the service or
prevent us from using it.

For now, these are the swagger links we've found:
* https://wapphqcdev01-automation.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-notification.azurewebsites.net/swagger/index.html
* https://wapphqcdev01-clientele.azurewebsites.net/swagger/index.html


# Contributing

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

## Collaborators

* [Francis Poisson](https://github.com/francispoisson/)
* [David Vallee Delisle](https://github.com/valleedelisle/)
