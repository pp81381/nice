[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Nice for Home Assistant

A Home Assistant Integration for the Nice TT6 control unit for tubular motors.

The Nice TT6 control unit is used to control projector screens, garage doors, awnings and blinds. It is white labelled by Screen Research as the MCS-N-12V-RS232 projector screen controller and by Beamax as the 11299 projector screen controller.

The control unit has an RS232 serial connection but is known to work with USB to serial converters.

## Controllers

The integration allows for multiple controllers.   Each controller can be added as a new configuration entry.

## Covers

The Integration allows for the control of multiple Covers per controller.   Each cover can be added as a configuration sub-entry of a controller.

The following Home Assistant entities are created for each Cover:

- A `cover` entity that can be used to control each Cover
- A `sensor` entity that represents the drop of the Cover

The Integration offers a service called [nice.set_drop_percent](#niceset_drop_percent) which will set the drop percentage to greater precision than the standard `cover.set_cover_position` service.

# Initial Configuration

## Step 1: Add a Controller

Add your first Controller to Home Assistant as follows:

- Navigate to Settings->Devices and Services
- Click on Add Integration
- Search for Nice
- Click on the Nice integration to initiate the configuration flow
- Enter a name for the controller and a serial port
- Click Submit to create the controller.  Note that the Integration will validate the controller at this point by trying to connect to it.

Examples of valid serial port definitions are:

- `/dev/ttyUSB0` (Linux)
- `COM3` (Windows)
- `socket://192.168.0.100:50000` (if you are using a TCP/IP to serial converter)

Additional controllers can be added the same way, or by clicking 'Add Hub' on the Nice integration page.

## Step 2: Add Cover(s)

From the Nice Integration page, click on 'Add Cover to Hub' and select the Controller if necessary.

Enter the following details:

| Field          | Description      |
|----------------|------------------|
| Cover Name     | Name of the Cover                          |
| Device Address | The TTBus address of the device<br>Get this from your vendor documentation - as an example, the projector screen might be device 2 and the mask might be device 3 |
| Device Node    | The TTBus node of the device<br>Again, get this from the documentation - usually 4      |
| Drop           | The maximum drop of the Cover in the unit system specified in the Integration definition                                           |
| Inverse Motor Endpoints?           | Normally, a native position of 1000 is fully up and 0 is fully down.<br>When inverted, 0 is fully up and 1000 is fully up.     |
| Inverse semantics?           | Normally, Opening is going up, Closing is going down and Closed is fully down.<br>When inverted, Opening is going down, Closing is going up, Closed is fully up.<br>Icons are also overridden.<br>Typically, this box would need to be checked for projector screens.     |

Click on Submit to create the Cover.

# Reconfiguration

## Reconfigure a Controller

Go to the Nice Integration page.  From the 3 dots next to the hub title, select "Reconfigure".   The name or serial port can be updated.

## Reconfigure a Cover

Go to the Nice Integration page.  Click on the cog icon next to the Cover sub entry title.   Any of the details can be updated.

# Services

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

## nice.refresh_position

Re-request the position of the selected cover

## nice.reconnect

Reconnect to the controller(s)

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

By default, the emulator will create four covers:

| Name | Address | Node | Description |
|------|---------|------|-------------|
| Screen | 2 | 4 | A projector screen |
| Mask | 3 | 4 | A mask for a projector screen |
| Blind | 10 | 4 | A blind with normal endpoints |
| Blind Inverted | 11 | 4 | A blind with inverted endpoints |

See the nicett6 documentation for more configuration options.