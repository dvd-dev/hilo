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

# :warning: Breaking change to come, please keep your component updated :warning:

The API we rely on for Hilo Challenges will be closed in the near future, we are currently working on an alternative
using Websockets/SignalR. **Updating to 2025.2.1 and later is strongly suggested** as prior versions will likely break due to the way
pip installs dependencies.

Several users and I are in the process of migrating our communications with the Hilo API to Websocket/SignalR instead of
API calls. This transition will be gradual, and we will do everything we can to avoid breaking existing installations.

The first step will be updating the `python-hilo` library (https://github.com/dvd-dev/python-hilo). This change should be
seamless for everyone.

Next, we will migrate the challenge sensor (`sensor.defi_hilo`) to Websocket/SignalR. The good news is that this method completely eliminates the temporary "glitches" that occurred with the challenge sensor.

### Remaining tasks:
- The `allowed_kWh` and `used_kWh` attributes are currently **non-functional**. The data arrives in fragments, and not all cases have been handled yet.
- The `"completed"` state does not always work, possibly due to a race condition.
- Some information, such as `total_devices`, `opt_out_devices`, and `pre_heat_devices`, does not persist in memory.

More details are available in **issue #486**.

The API used for the initial retrieval of the device list on your Hilo account will also undergo the same transition.

More details are available in **issue #564**.

## Introduction

This is the unofficial HACS Hilo integration for Home Assistant. [Hilo](https://www.hiloenergie.com/en-ca/) is a smart home platform developed
by a [Hydro Quebec](https://www.hydroquebec.com/hilo/en/) subsidiary.
This integration has no direct tie with Hilo or Hydro Quebec. This is a community initiative. Please don't contact
Hilo or Hydro-Quebec with issues with this Home Assistant integration, you can open an issue in the GitHub repository
instead.

If you want to help with the development of this integration, you can always submit a feedback form from the Hilo
application and requesting that they open their API publicly and that they provide a testing environment to the
developers.

### TL:DR version:

You can find a recommended minimal configuration [in the wiki](https://github.com/dvd-dev/hilo/wiki/FAQ#do-you-have-any-recommended-settings)


You can also find sample automations in YAML format [in the doc/automations directory](https://github.com/dvd-dev/hilo/tree/main/doc/automations)
If you prefer blueprints, there are some available here:
  - [NumerID's repository](https://github.com/NumerID/blueprint_hilo)
  - [Arim215's repository](https://github.com/arim215/ha-hilo-blueprints)

### Shout out

Big shout out to [Francis Poisson](https://github.com/francispoisson/) who's the original author of this integration. Without the work
he put into this integration, I would probably have never even considered Hilo.

Another big shout out to @ic-dev21 for his implication at multiple levels.

I decided to move the integration here because of the latest updates from Hilo broke the original one, and I took the time to completely
rewrite it. Hilo is now pushing device readings via websocket from SignalR.

### Features
- Support for switches and dimmers as light devices
- Get current and set target temperature of thermostat
- Get energy usage of pretty much each device
- Generates energy meters and sensors
- Sensor for Hilo Events (challenges)
- Sensor for Hilo Gateway
- Now configuration is done via the UI
- Updates are now closer to realtime
- **NEW**: Authentication directly on Hilo's website
- **NEW**: Outdoor weather sensor with changing icon like in the Hilo App

### To Do:
- Add functionalities for other devices
- unit and functional tests
- [Adding type hints to the code](https://developers.home-assistant.io/docs/development_typing/)
- API calls to Hilo documentation now available [here](https://github.com/dvd-dev/python-hilo)
- Map send energy meters automatically to energy dashboard


## Installation

### Step 0: Compatible install
This custom component requires that Hilo has carried out the installation in your home. It will not be possible to set it up otherwise.

This custom component has been tested to work by various users on HA OS (as bare metal or VM), Docker with the official (ghcr.io) image and Podman. Other types of install may cause permission issues during the creation of a few files needed by the custom component.

### Step 1: Download files

#### Option 1: Via HACS

[![Open Hilo inside your Home Assistant Community Store (HACS).](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dvd-dev&repository=hilo&category=integration)

Make sure you have [HACS](https://hacs.xyz/docs/setup/download/) installed.
Under HACS, click the '+ EXPLORE & DOWNLOAD REPOSITORIES' button on the bottom of the page, search for "Hilo", choose it, and click _download_ in HACS.

#### Option 2: Manual

Download and copy the `custom_components/hilo` directory from the [latest release](https://github.com/dvd-dev/hilo/releases/latest) to your `custom_components` directory in HA.

### Step 2: Add integration to HA (<--- this is a step that a lot of people forget)

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hilo)

In HA, go to Settings > Devices & Services > Integrations.
In the bottom right corner, click the '+ ADD INTEGRATION' button.

![Add Integration](https://github.com/dvd-dev/hilo/assets/108159253/7906f2c9-9547-4478-a625-feaa68e62c5f)

If the component is properly installed, you should be able to find the 'Hilo integration' in the list. You might need to clear your browser cache for the integration to show up.

![Search Integration](https://github.com/dvd-dev/hilo/assets/108159253/1b560a73-042b-46cf-963c-98e5326e98e8)


## Configuration (new install)

The configuration is done in the UI. When you add the integration, you will be redirected to Hilo's website login page to authenticate.

![Open Website](https://github.com/dvd-dev/hilo/assets/108159253/23b4fb34-f8c3-40b3-8e01-b3e737cc9d44)


![Auth Hilo](https://github.com/dvd-dev/hilo/assets/108159253/e4e98b32-78d0-4c49-a2d7-3bd0ae95e9e0)

You must then accept to link your account. To do so, you must enter your Home Assistant instance's URL or IP address and click Link Account.

![Link](https://github.com/dvd-dev/hilo/assets/108159253/5eb945f7-fa5e-458f-b0fe-ef252aaadf93)

![Link URL](https://github.com/dvd-dev/hilo/assets/108159253/2c54df64-2e1c-423c-89cf-0eee8f0d4b7b)

After this, you will be prompted to assign a room for each one of your devices.

## Configuration (update from a version earlier than v2024.3.1)

After update, you will get an error saying you must reauthenticate for the integration to work.

![Reconfiguration 2](https://github.com/dvd-dev/hilo/assets/108159253/a711d011-17a9-456f-abf6-74cf099014f1)

![Reath](https://github.com/dvd-dev/hilo/assets/108159253/70118e68-90b9-4667-b056-38ee2cd33133)

After correctly linking your account like in the previous section, you should see a popup telling you the reauthentification was successful.

### Energy meters

Energy meters are a feature of this integration. We used to manually generate them with template sensors and automation,
but they now have been fully integrated into the Hilo integration.

#### Warning

When enabling Hilo generated energy meters, it's recommended to remove the manually generated ones to have the most accurate
statistics, otherwise we might end up with duplicated data.

If you're facing an issue, and you want to collaborate, please enable `debug` log level for this integration and provide a copy
of the `home-assistant.log` file. Details on how to enable `debug` are [below](https://github.com/dvd-dev/hilo/blob/main/README.en.md#contributing).

#### Procedure

If you want to enable the automatic generation of the energy sensors, follow these steps:

* Make sure that the `utility_meter` platform is loaded in your `configuration.yaml` file from
home assistant. You simply need to add a line like this in your `configuration.yaml`:

    ```
    utility_meter:
    ```

* Click`Configure` on the integration UI and check the `Generate energy meters` box.

* Restart home assistant and wait 5 minutes until you see the `sensor.hilo_energy_total_low` entity getting created and populated
  with data:
  * The `status` should be in `collecting`
  * The `state` should be a number higher than 0.

* All generated entities and sensors will be prefixed or suffixed with `hilo_energy_` or `hilo_rate_`.

* If you see the following error in your logs, this is a bug in Home Assistant, and it's because the power meter in question has 0 W/h
  usage so far. This will disappear once usage has been calculated.

    ```
    2021-11-29 22:03:46 ERROR (MainThread) [homeassistant] Error doing job: Task exception was never retrieved
    Traceback (most recent call last):
    [...]
    ValueError: could not convert string to float: 'None'
    ```
Once created, energy meters will then have to be added manually to the energy dashboard.


### Other configurations

Other options are available under the `Configure` button in Home Assistant:

- `Generate energy meters`: Checkbox

  Automatically generate energy meters, see procedure above for proper setup
  Requires this line to be added to your configuration.yaml file:
  ```
  utility_meter:
  ```

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

- `appreciation phase`: Integer (hours)

  Add an appreciation phase of X hours before the preheat phase.

- `pre_cold phase`: Integer (hours)

  Add a cooldown phase of X hours to reduce temperatures before the appreciation phase

- `Scan interval (min: 60s)`: Integer

  Number of seconds between each device update. Defaults to 60 and, it's not recommended to go below 30 as it might
  result in a suspension from Hilo. Since [2023.11.1](https://github.com/dvd-dev/hilo/releases/tag/v2023.11.1) the minimum has changed from 15s to 60s.

## Lovelace sample integration and automation example

You can find multiple examples and ideas for lovelace dashboard, cards and automation here [in the wiki of the project](https://github.com/dvd-dev/hilo/wiki/Utilisation)

You can also find sample automations in YAML format [in the doc/automations directory](https://github.com/dvd-dev/hilo/tree/main/doc/automations)


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

Reporting any kind of issue is a good way of contributing to the project, and it's available to anyone.

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

### Prepare a development environment via VSCode DevContainer

To facilitate development, a development environment is available via VSCode DevContainer. To use it, you must have [VSCode](https://code.visualstudio.com/) and [Docker](https://www.docker.com/) installed on your computer.

1. Open the project folder in VSCode
2. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
3. If you want to work on `python-hilo` at the same time, you need to clone the [python-hilo repository](https://github.com/dvd-dev/python-hilo) in a folder adjacent to the `hilo` folder. The `python-hilo` folder name is **REQUIRED** for the development environment to work properly. ex:

        parent_folder/
        ├── hilo/
        └── python-hilo/

3. Open the command palette (Ctrl+Shift+P or Cmd+Shift+P) and search for "Remote-Containers: Reopen in Container"
4. Wait for the environment to be ready
5. Open a terminal in VSCode and run `scripts/develop` to install dependencies and start Home Assistant
6. At this point, VSCode should prompt you to open a browser to access Home Assistant. You can also open a browser manually and go to [http://localhost:8123](http://localhost:8123)
7. You will need to do the initial Home Assistant configuration
8. You will need to add the Hilo integration via the user interface
9. You can now modify files in the `custom_components/hilo` folder and see changes in real-time in Home Assistant
10. In the terminal where you launched `scripts/develop`, Home Assistant and HILO integration logs should be streamed

### Before submitting a Pull Request

It goes without saying you must test your modifications on your local install for problems. You may modify the .py files inside the following folder. Don't forget a backup!
```
custom_components/hilo
```

If you need to modify python-hilo for your tests, you can pull your own fork into Home Assistant with the following on the CLI:

```
pip install -e git+https://github.com/YOUR_FORK_HERE/python-hilo.git#egg=python-hilo
```

You must then restart Home Assistant for your install to take effect. To go back to the original, simply type:

```
pip install python-hilo
```
And restart Home Assistant

### Submitting a Pull Request

- First you need to `fork` the repository into your own userspace.
- And then, you can `clone` it on your computer.
- To maintain some kind of tidiness and standard in the code, we have some linters and validators that need to be executed via `pre-commit` hooks:
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
- Finally, you can `push` the change in your upstream repository:
```
git push
```
- At this point, if you visit the [upstream repository](https://github.com/dvd-dev/hilo), GitHub should prompt you to create a Pull Request (aka PR). Just follow the instructions.

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
