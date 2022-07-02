# Experimenting with the Pi Pico

## gpioCtl

This is a utility that allows setting or clearing of all GPIO on the board. This is useful, for example, when you want to depower peripherals but not the Pico. You wouldn't want to drive unpowered peripheral IO, so run `gpioCtl.setAll(0)` or `gpioCtl.outDrive(0)` prior to doing so.

## hd44780

This implements both the 4-bit and 8-bit interfaces, with and without R/Wn, to the HD44780 LCD
driver IC commonly used in small dot matrix displays, like those included with certain hobbyist
prototyping kits.

<p align="center">
  <img src="doc/example.gif" width="400"/>
</p>

### Build Status

Both 4- and 8-bit modes have been tested with `R/W'` connected (`RWn_CONNECTED = True`) as well as `R/W'` tied to ground (`RWn_CONNECTED = False`). This covers all 4 possible configurations.

However, actually reading the `Busy` bit and register values is unimplemented. When enabled, the code just switches GPIO directions so that the data could be read.

### Configuration

See `User Configuration` section for user-controlled parameters. You MUST set the following, at minimum:
* LOC_DATA is a 4- or 8-entry list of **GP** numbers where you have connected your data interface bits. These **are not** pin numbers, they are GPIO indices.
* LOC_E is the **GP** number of the `E` bit.
* LOC_RS is the **GP** number of the `RS` bit.

Optionally, you may connect the `R/W'` pin and set `RWn_CONNECTED` to `True` to enable reading from the device.

### Usage

See `Program Entry` section for an example. In some cases, you will interact directly with the LCD by issuing commands like `DISPLAY_ON` or `DISPLAY_CLEAR`, but in others you may use a more abstract method like `putLine`, which effectively issues a number of character write commands.

Decorative printing is also included by setting the `effect` bit in `putLine()` or pushing text to the display using `pushLine`, which creates a scrolling effect as lines are added

## HowTo

### Work with the remote Pico filesystem

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
