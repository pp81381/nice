[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Nice for Home Assistant

A Home Assistant Integration for the Nice TT6 control unit for tubular motors.

The Nice TT6 control unit is used to control projector screens, garage doors, awnings and blinds. It is white labelled by Screen Research as the MCS-N-12V-RS232 projector screen controller and by Beamax as the 11299 projector screen controller.

The control unit has an RS232 serial connection but is known to work with USB to serial converters.

## Covers

The Integration allows for the control of multiple Covers. There can be one or many control units, each controlling one or many Covers.

The following Home Assistant entities are created for each Cover:

- A `cover` entity that can be used to control each Cover
- A `sensor` entity that represents the drop of the Cover

The Integration offers a service called [nice.set_drop_percent](#niceset_drop_percent) which will set the drop percentage to greater precision than the standard `cover.set_cover_position` service.

## Presets

The Integration offers a service called [nice.apply_preset](#niceapply_preset) which will move any number of Covers to preset positions.

## Projector Screen Control

The Integration was designed with projector screens in mind and offers some optional features for controlling multiple Covers in a Constant Image Width (CIW) configuration.

A Cover can optionally have an Image Area defined to represent the screen. An optional helper called a "CIW Manager" can be defined which links a Cover that is a Screen and a Cover that is a Mask. The following `sensor` entities are created for each "CIW Manager":

- Image Height
- Image Width
- Image Diagonal
- Aspect Ratio

The Integration offers a service called [nice.set_aspect_ratio](#niceset_aspect_ratio) which will set the Covers managed by a CIW Manager to a specific Aspect Ratio.

## Sensors

The sensors all round their values to 2 decimal places. They also offer a state variable called `full_precision_value` that is not rounded.

# Initial Configuration

## Step 1: Add the Integration

Add the Integration to Home Assistant as follows:

- Navigate to Configuration->Integrations
- Click on Add Integration
- Search for Nice
- Click on the Nice integration to initiate the configuration flow

## Step 2: Integration Definition

Enter the details of the Integration:

| Field       | Description                            |
| ----------- | -------------------------------------- |
| Title       | The title of the integration           |

Click Submit to move to the next step.

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
| Drop           | The maximum drop of the Cover in the unit system specified in the Integration definition                                                                          |
| Image Area     | Check this box if the Cover is a screen<br>If the Cover has an Image Area then additional details will be collected in the next step                              |

Click on Submit to move to the next step.

## Step 4b: Define Image Area

If the Cover has an Image Area then enter the following details:

| Field        | Description                                                                                     |
| ------------ | ----------------------------------------------------------------------------------------------- |
| Border Below | Height of the border below the image in the unit system specified in the Integration definition |
| Height       | The height of the Image Area in the unit system specified in the Integration definition         |
| Aspect Ratio | The Aspect Ratio                                                                                |

Height plus the Border Below cannot be larger than the maximum drop defined in the previous step.

Click on Submit to move to the next step.

## Step 5: Finish Cover

If there is another Cover to be created then check "Add Another Cover?"

Click on Submit to either create another Cover or finish the configuration.

# Options

## Options Menu

Navigate to Configuration->Integrations, locate the Nice Integration and click on "Configure". The following options can be seleced from the "Choose Action" screen.

| Option             | Description                                                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Add CIW Manager    | Add a CIW Manager<br>This option is shown if there is at least one Cover with an Image Area (a Screen) and one without (a Mask). |
| Del CIW Manager    | Delete a CIW Manager<br>This option is only shown if any CIW Managers exist.                                                     |
| Add Preset         | Add a Preset                                                                                                                     |
| Del Preset         | Delete a Preset<br>This option is only shown if any Presets exist.                                                               |

Select an option and click on Submit to move to the next step.

## Adding a CIW Manager

Enter the following details and then click on Submit to create the CIW Manager.

| Field             | Description                                                                                                                                                       |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Name              | A friendly name for the Object                                                                                                                                    |
| Screen            | Name of the screen<br>Only Covers with an Image Area can be selected                                                                                              |
| Mask              | Name of the mask<br>Only covers without an image Area can be selected                                                                                             |

## Deleting CIW Managers

Select the CIW Manager(s) to be deleted. Click on Submit to delete them.

## Adding a Preset

Give the Preset a name and select the list of Covers to be moved. Click Submit to define the drop for each Cover in turn.

## Deleting Presets

Select the Preset(s) to be deleted. Click on Submit to delete them.

# Services

## nice.apply_preset

Takes the name of the Preset as the argument

## nice.set_drop_percent

Takes a Cover entity and the percentage drop as parameters. This service will set the drop to an accuracy of up to 0.1% as opposed to the `cover.set_current_position` service which uses an `int` to specify the position.

## nice.send_simple_command

Takes a Cover entity and the command name as parameters.

Valid commands are as follows.  

```json
"options": {
    "stop": "Stop",
    "move_down": "Move down",
    "move_up": "Move up",
    "move_pos_1": "Move to built-in preset 1",
    "move_pos_2": "Move to built-in preset 2",
    "move_pos_3": "Move to built-in preset 3",
    "move_pos_4": "Move to built-in preset 4",
    "move_pos_5": "Move to built-in preset 5",
    "move_pos_6": "Move to built-in preset 6",
    "move_up_step": "Move up a step",
    "move_down_step": "Move down a step",
    "store_pos_1": "Store current position in built-in preset 1",
    "store_pos_2": "Store current position in built-in preset 2",
    "store_pos_3": "Store current position in built-in preset 3",
    "store_pos_4": "Store current position in built-in preset 4",
    "store_pos_5": "Store current position in built-in preset 5",
    "store_pos_6": "Store current position in built-in preset 6",
    "del_pos_1": "Delete built-in preset 1",
    "del_pos_2": "Delete built-in preset 2",
    "del_pos_3": "Delete built-in preset 3",
    "del_pos_4": "Delete built-in preset 4",
    "del_pos_5": "Delete built-in preset 5",
    "del_pos_6": "Delete built-in preset 6"
}
```

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
