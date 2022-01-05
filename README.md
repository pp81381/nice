[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Nice for Home Assistant

A Home Assistant Integration for the Nice TT6 control unit for tubular motors.

The Nice TT6 control unit is used to control projector screens, garage doors, awnings and blinds. It is white labelled by Screen Research as the MCS-N-12V-RS232 projector screen controller and by Beamax as the 11299 projector screen controller.

The control unit has an RS232 serial connection but is known to work with USB to serial converters.

## Covers

The Integration allows for the control of multiple Covers. There can be one or many control units, each controlling one or many Covers. The following Home Assistant entities are created for each Cover:

- A `cover` entity that can be used to control each Cover
- A `sensor` entity that represents the drop of the Cover in metres

## Presets

The Integration offers a service called [nice.apply_preset](#niceapply_preset) which will move any number of Covers to preset positions.

## Projector Screen Control

The Integration was designed with projector screens in mind and offers some optional features for controlling multiple Covers in a Constant Image Width (CIW) configuration.

A Cover can optionally have an Image Area defined to represent the screen. An optional helper called a "CIW Manager" can be defined which links a Cover that is a Screen and a Cover that is a Mask. The following `sensor` entities are created for each "CIW Manager":

- Image Height in metres
- Image Width in metres
- Image Diagonal in metres
- Image Area in square metres
- Aspect Ratio

The Integration offers a service called [nice.set_aspect_ratio](#niceset_aspect_ratio) which will set the Covers managed by a CIW Manager to a specific Aspect Ratio.

# Initial Configuration

## Step 1: Add the Integration

Add the Integration to Home Assistant as follows:

- Navigate to Configuration->Integrations
- Click on Add Integration
- Search for Nice
- Click on the Nice integration to initiate the configuration flow

## Step 2: Integration Definition

Enter the title of the integration and click Submit

## Step 3: Create Controller(s)

Enter a name for the controller and the serial port.

Examples of valid serial port definitions are:

- `/dev/ttyUSB0` (Linux)
- `COM3` (Windows)
- `socket://192.168.0.100:50000` (if you are using a TCP/IP to serial converter)

If there is another controller to be added then check the box "Add Another Controller?"

Click Submit to move to the next step or create another controller as appropriate. Note that the Integration will validate the controller at this point by trying to connect to it.

## Step 4a: Create Cover

Enter the following details:

| Field          | Description                                                                                                                                                       |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cover Name     | Name of the Cover                                                                                                                                                 |
| Controller     | The Controller<br>Select from a drop down list                                                                                                                    |
| Device Address | The TTBus address of the device<br>Get this from your vendor documentation - as an example, the projector screen might be device 2 and the mask might be device 3 |
| Device Node    | The TTBus node of the device<br>Again, get this from the documentation - usually 4                                                                                |
| Drop           | The maximum drop of the Cover in metres                                                                                                                           |
| Image Area     | Check this box if the Cover is a screen<br>If the Cover has an Image Area then additional details will be collected in the next step                              |

Click on Submit to move to the next step.

## Step 4b: Define Image Area

If the Cover has an Image Area then enter the following details:

| Field        | Description                                    |
| ------------ | ---------------------------------------------- |
| Border Below | Height of the border below the image in metres |
| Height       | The height of the Image Area in metres         |
| Aspect Ratio | The Aspect Ratio                               |

Height plus the Border Below cannot be larger than the maximum drop defined in the previous step.

Click on Submit to move to the next step.

## Step 5: Finish Cover

If there is another Cover to be created then check "Add Another Cover?"

Click on Submit to either create another Cover or finish the configuration.

# Options

## Options Menu

Navigate to Configuration->Integrations, locate the Nice Integration and click on "Configure". The following options can be seleced from the "Choose Action" screen.

| Option          | Description                                                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Add CIW Manager | Add a CIW Manager<br>This option is shown if there is at least one Cover with an Image Area (a Screen) and one without (a Mask). |
| Del CIW Manager | Delete a CIW Manager<br>This option is only shown if any CIW Managers exist.                                                     |
| Add Preset      | Add a Preset                                                                                                                     |
| Del Preset      | Delete a Preset<br>This option is only shown if any Presets exist.                                                               |

Select an option and click on Submit to move to the next step.

## Adding a CIW Manager

Enter the following details and then click on Submit to create the CIW Manager.

| Field             | Description                                                                                                                                        |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Name              | A friendly name for the Object                                                                                                                     |
| Screen            | Name of the screen<br>Only Covers with an Image Area can be selected                                                                               |
| Mask              | Name of the mask<br>Only covers without an image Area can be selected                                                                              |
| Aspect Ratio Mode | Specifies whether the top, middle or bottom of the resulting image area will be held constant relative to the baseline as the aspect ratio changes |
| Baseline Drop     | Fixed drop in metres to be used as a baseline when setting the aspect ratio<br>Will be defaulted if left blank                                     |

Note that the Baseline Drop field is defaulted/validated as follows:

| Aspect Ratio Mode | Default Baseline Drop                                       | Validation Rule                                                                                                                                                                 |
| ----------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FIXED_TOP         | Top of the Image Area when the Screen is fully down         | Min:0.0<br>Max: Maximum Drop of the Mask                                                                                                                                        |
| FIXED_MIDDLE      | Centre line of the Image Area when the screen is fully down | Min: Centre line of minimum-height valid Image where Image Area is as high as possible<br>Max: Centre line of minimum-height valid Image where Image Area is as low as possible |
| FIXED_BOTTOM      | Bottom of the Image Area when the Screen is fully down      | Min: Bottom of minimum-height valid Image where Image Area is as high as possible<br>Max: Bottom of minimum-height valid Image where Image Area is as low as possible           |

Note that the minimum height of the Image Area corresponds to an aspect ratio of 3.5.

## Deleting CIW Managers

Select the CIW Manager(s) to be deleted. Click on Submit to delete them.

## Adding a Preset

Give the Preset a name and select the list of Covers to be moved. Click Submit to define the drop for each Cover in turn.

## Deleting Presets

Select the Preset(s) to be deleted. Click on Submit to delete them.

# Services

## nice.apply_preset

Takes the name of the Preset as the argument

## nice.set_aspect_ratio

Takes the name of the CIW Manager and the desired aspect ratio as parameters.

The CIW Manager will move the screen and mask to achieve the requested aspect ratio. The CIW manager uses two internal parameters, the mode and the baseline_drop, to determine the positions of the screen and mask. The baseline_drop is a fixed drop to be used as a baseline. The mode specifies whether the top, middle or bottom of the resulting image area will be held constant relative to the baseline.

# Emulator

If you would like to experiment with this integration then you can run an emulator of the Nice TT6 controller.

Set it up as follows:

```shell
python -m venv nice_venv
source nice_venv/bin/activate
pip install nicett6_pp81381
```

Run it as follows:

```shell
source nice_venv/bin/activate
python -m nicett6.emulator
```

Use it by configuring a Controller with a serial port like `socket://localhost:50200`
