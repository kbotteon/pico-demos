# Experimenting with the Pi Pico

## GPIO Control

|||
|-:|:-|
| Implemented In | `gpioCtl.py`
| Example In |

This is a utility that allows setting or clearing of all GPIO on the board. This is useful, for example, when you want to depower peripherals but not the Pico. You wouldn't want to drive unpowered peripheral IO, so run `gpioCtl.setAll(0)` or `gpioCtl.outDrive(0)` prior to doing so.

## LCD Control

|||
|-:|:-|
| Implemented In | `hd44780.py`
| Example In | `demo.py`

This implements both the 4-bit and 8-bit interfaces, with and without R/Wn, to the HD44780 LCD
driver IC commonly used in small dot matrix displays, like those included with certain hobbyist
prototyping kits.

<p align="center">
  <img src="doc/example.gif" width="400"/>
</p>

### Status

Both 4- and 8-bit modes have been tested with `R/W'` connected (`RWn_CONNECTED = True`) as well as `R/W'` tied to ground (`RWn_CONNECTED = False`). This covers all 4 possible configurations.

However, actually reading the `Busy` bit and register values is unimplemented. When enabled, the code just switches GPIO directions so that the data could be read.

### Configuration

See `User Configuration` section for user-controlled parameters. You MUST set the following, at minimum:
* LOC_DATA is a 4- or 8-entry list of **GP** numbers where you have connected your data interface bits. These **are not** pin numbers, they are GPIO indices.
* LOC_E is the **GP** number of the `E` bit.
* LOC_RS is the **GP** number of the `RS` bit.

Optionally, you may connect the `R/W'` pin and set `RWn_CONNECTED` to `True` to enable reading from the device.

### Usage

See `demo.py` for an example. In summary, from the `src` directory and with `mpremote` installed, you can:

```
mpremote fs cp hd44780.py :/
mpremote run demo.py
```

## Background

### Working with the Remote Pico Filesystem

Scripts with no arguments can be executed with
```
mpremote run <script.py>
```

Or, copy your local file to the Pico
```
mpremote fs cp file.py :/
```

Verify it and any supporting files exist
```
mpremote fs ls
```

Then run call whatever functions you need from REPL
```
mpremote exec "import gpioCtl; gpioCtl.setAll(0)"
```
