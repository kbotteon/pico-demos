# hd44780.py
#
# A MicroPython implementation of the HD44780 LCD driver interface for a Pi Pico
#
################################################################################
# Copyright 2022 Kyle Botteon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

from machine import Pin as Pico_Pin
from utime import sleep_us, sleep_ms

################################################################################
# User Configuration
################################################################################

# Pi Pico GP number (not pin number!) of data pins
# Define [ D0, D1, D2, D3, D4, D5, D6, D7 ] to use 8-bit mode or
# [ D4, D5, D6, D7 ] for 4-bit mode; reset() and send() adjusts accordingly

# LOC_DATA = [6, 7, 8, 9, 10, 11, 12, 13]
LOC_DATA = [10, 11, 12, 13]

# GP number of LCD E, RS, and R/W' pins
# You *might* be able to get away without R/W' by tieing it to ground, leaving
# write mode always enabled
LOC_E = 14
LOC_RS = 15
LOC_RWn = 16

# Set this to False if for some reason you chose not to connect the R/W' pin
RWn_CONNECTED = False

# The address space the display character array exists within
# Don't change this if you have a 2x16 display, otherwise update per datasheet
DRAM_RANGE = {
    'l1_start': 0x00,
    'l1_end': 0x27,
    'l2_start': 0x40,
    'l2_end': 0x67
}

################################################################################
# Constants
################################################################################

# LCD opcodes and execution times
# See datasheet p. 24
# key: [opcode, duration in us]
# FIXME: Can we combine opcode and duration into one table?
COMMANDS = {
    # Not a command, but a default wait time when needed
    'DEFAULT': [0x00, 37],
    'DISPLAY_ON': [0x0E, 37],
    'DISPLAY_OFF': [0x08, 37],
    # Duration for this one isn't actually specified, so assume a similar duration to Return Home
    # becuase the underlying operations are basically the same
    'DISPLAY_CLEAR': [0x01, 1500],
    'CURSOR_HOME': [0x02, 1520],
    'MODE_AUTOINC': [0x06, 4],
    # 8-bit mode, 2 lines, 5x8 display
    'FUNCSEL_8BIT': [0x38, 37],
    # 4-bit mode, 2 lines, 5x8 display
    'FUNCSEL_4BIT': [0x28, 37],
    'DDRAM_SET': [0x80, 37]
}

################################################################################
# Globals
################################################################################

# Hardware interfaces via 'machine'
if RWn_CONNECTED:
    PinCtl = [Pico_Pin(pinNo, Pico_Pin.IN, value=0) for pinNo in LOC_DATA] # Default IN
else:
    PinCtl = [Pico_Pin(pinNo, Pico_Pin.OUT, value=0) for pinNo in LOC_DATA] # Default OUT

Pin_E = Pico_Pin(LOC_E, Pico_Pin.OUT, value=1) # If it's high, don't drive low and trigger LCD input
Pin_RS = Pico_Pin(LOC_RS, Pico_Pin.OUT, value=0)

if RWn_CONNECTED:
    Pin_RWn = Pico_Pin(LOC_RWn, Pico_Pin.OUT, value=1) # Default to WRITE mode so IC does not drive bus

# Local storage for whatever is presently on screen
# Start with 16 blank spaces, and pad it so indices [1] and [2] line up with the
# physical line numbers
LineVal = [ "", " "*16, " "*16 ]

# This will be set automatically later by premain() based on LOC_DATA size
# The LCD IC always starts in 8-bit mode and must be transitioned
# Options: 8BIT or 4BIT
INTERFACE_MODE = "8BIT"

# This is shared among functions to determine whether a GPIO direction swap
# should be performed; that takes time, so avoid when possible
if RWn_CONNECTED:
    GPIO_OUT_EN = False
else:
    GPIO_OUT_EN = True

################################################################################
# Implementation
################################################################################

# Direction swapping for bidirectional bus
def enGpioOut(enable):
    global GPIO_OUT_EN

    if(enable):
        GPIO_OUT_EN = True
        # Ensure the bus won't be driven in contention, if we control it
        if RWn_CONNECTED:
            Pin_RWn.low() # LCD write mode expects Pico to drive bus
        # Reconfigure the data GPIO as outputs
        PinCtl = [Pico_Pin(pinNo, Pico_Pin.OUT, value=0) for pinNo in LOC_DATA]
    else:
        GPIO_OUT_EN = False
        # Ensure the bus won't be driven in contention, if we control it
        if RWn_CONNECTED:
            Pin_RWn.high() # LCD read mode will drive bus
        # Reconfigure the data GPIO as inputs
        PinCtl = [Pico_Pin(pinNo, Pico_Pin.IN, Pico_Pin.PULL_DOWN) for pinNo in LOC_DATA]

# Read from HD44780
#
# See datasheet p.33, 4 bit operation
#
# Steps:
#
def read():

    # If there is not pin to toggle R/W mode, this isn't going to work, otherwise
    # enter READ mode
    if not RWn_CONNECTED:
        raise Exception("Can't read without a RWn pin")

    # See if the GPIO outputs are enabled, and disable those if so
    if GPIO_OUT_EN:
        enGpioOut(False)

    # Must do this AFTER setting the GPIO to inputs so we don't drive in contention
    Pin_RWn.high()

    # Generate the control signals for a read
    Pin_RS.low() # If this is high, it reads the data register instead of 'busy' and 'addr'
    Pin_E.high()
    sleep_us(1) # Enable to data output delay and minimum intra-enable cycle time

    # Data is valid by now, read it and drop enable for the next caller to get updated value
    data = 0
    for elem in PinCtl:
        data = data | (elem.value() << PinCtl.index(elem))
    Pin_E.low()
    sleep_us(1)

    # Return 4 or 8 bits depending on mode; do NOT automatically do an 8-bit read
    # in 4-bit mode, because the user does not need that to check the BUSY flag
    return data

# Write to HD44780
#
# See datasheet p.58 for timing diagrams
#
# Steps:
#   1. Assert RS and R/W'
#   2. Wait 40ns
#   3. Assert Enable
#   4. Assert data bits
#   5. Wait 230ns (min enable pulse is longer than data setup)
#   6. Deassert Enable. Data is latched
#   7. Hold data 10ns
#   8. Wait until 1us has elapsed since step 3
#
# FIXME: Datasheet says we must check the busy flag via a read before proceeding
def write(u8, isCmd: "T/F", exeTime: 'in microseconds'):

    # Verify busy is not asserted
    if RWn_CONNECTED:
        val = read()
        # TODO: If the busy flag is actually set...which it should never be
        # Must do this BEFORE enabling GPIO outputs so we dont' drive in contention
        Pin_RWn.low()

    # If the outputs are not enabled, switch modes
    if not GPIO_OUT_EN:
        enGpioOut(True)

    # R/S = 0 for command or 1 for data
    if isCmd:
        Pin_RS.low()
    else:
        Pin_RS.high()

    # E \_ latches data, and the datasheet doesn't specify a /^ to data
    # time, so it should be safe to drive this high now
    Pin_E.high()

    if INTERFACE_MODE == "8BIT":
        # For each Pin bit, see if it should be asserted or not and do so
        for elem in PinCtl:
            if (u8 >> PinCtl.index(elem)) & 0x1 == 0x1:
                elem.high()
            else:
                elem.low()

    elif INTERFACE_MODE == "4BIT":
        CMD_HI = (u8 >> 4) & 0xF
        CMD_LO = u8 & 0xF
        # Send the upper 4 bits of command
        for elem in PinCtl:
            if (CMD_HI >> PinCtl.index(elem)) & 0x1 == 0x1:
                elem.high()
            else:
                elem.low()
        sleep_us(1) # Min E pulse and addr setup time
        Pin_E.low()
        sleep_us(1) # Intra-enable pulse time
        # Now send the lower 4 bits of command
        Pin_E.high()
        for elem in PinCtl:
            if (CMD_LO >> PinCtl.index(elem)) & 0x1 == 0x1:
                elem.high()
            else:
                elem.low()

    else:
        raise Exception("Valid mode options are 8BIT and 4BIT")

    # 230 ns minimum enable pulse time
    sleep_us(1)
    Pin_E.low()

    # Exit write mode
    if RWn_CONNECTED:
        Pin_RWn.low()

    # 1 us minimum intra-enable pulse time, plus command execution time
    sleep_us(1 + exeTime)

# Make it a little easier to send commands by wrapping the lookup of opcode and duration
def cmd(name):
    params = COMMANDS.get(name)
    write(params[0], True, params[1])

# The chip has a POR, but can be re-initialized with instructions if necessary
# The sequence is:
#   * Set RS = 0, R/W' = 0
#   * Write 0x30
#   * Wait 4.1 ms
#   * Write 0x30
#   * Wait 100 us
#   * Write 0x38 (N = 1, F = 0)
#   * Write 0x0F
#   * Write 0x01
#   * Write 0x07 (I/D = 1, S = 1)
def resetLcd():

    # We're going to adjust this if PinCtl only has enough pins defined to run 4-bit mode,
    # but only after first using the default 8-bit utilities to reset and change modes
    global INTERFACE_MODE

    # Reset the device depending on the number of pins connected
    if len(PinCtl) == 8:
        write(0x30, True, 4100)
        write(0x30, True, 100)
        write(0x30, True, 100)
        # This can only be set during reset sequence or immediately after power on
        cmd('FUNCSEL_8BIT')
        INTERFACE_MODE = "8BIT"

    elif len(PinCtl) == 4:
        # Borrow 8-bit mode in send() to do the unique 4-bit reset sequence; see p. 46
        write(0x3, True, 4100)
        write(0x3, True, 100)
        write(0x2, True, 100)
        write(0x2, True, 100)
        # This can only be set during reset sequence or immediately after power on
        cmd('FUNCSEL_4BIT')
        # Now we're in 4-bit mode; say tell send() it should use that mode
        INTERFACE_MODE = "4BIT"

    else:
        raise Exception("Generate PinCtl with a valid number of control pins: 4 or 8")

    # These default settings can be changed later
    cmd('DISPLAY_OFF')
    cmd('DISPLAY_CLEAR')
    cmd('MODE_AUTOINC')

#
# Line manipulation
#

# Write a character to the cursor location
def putChar(char):
  binVal = ord(char)
  write(binVal, False, COMMANDS.get("DEFAULT")[0])


# Set the display line
def setLine(line: "1 or 2"):

    # Arg check
    valid = {1, 2}
    if line not in valid:
      raise ValueError("Valid range is 1:2")

    # Generate commands
    # D7 = 1
    # D6:0 = ADDR
    if line == 1:
        DRAM_ADDR_CMD = COMMANDS.get("DDRAM_SET")[0] | DRAM_RANGE.get('l1_start')
    else:
        DRAM_ADDR_CMD = COMMANDS.get("DDRAM_SET")[0] | DRAM_RANGE.get('l2_start')

    write(DRAM_ADDR_CMD, True, COMMANDS.get("DDRAM_SET")[1])

# Write a string to a line on the display
def putLine(line, string, effect: "Typewriter effect T/F"):
    setLine(line)
    LineVal[line] = string
    # We can sequentially enter data immediately after a setLine()
    for char in string:
        putChar(char)
        if effect:
            sleep_ms(110) # Seems to be a nice speed for typing effect

def clearLine(line):
    putLine(line, " "*16, False)

# Scroll effect: push a new line of text onto the bottom of the screen, moving
# the current bottom line to the top
def pushLine(string, effect: "Typewriter effect T/F"):
    # Move line 2 to line 1, never use character typing effect for this
    clearLine(1)
    LineVal[1] = LineVal[2]
    putLine(1, LineVal[1], False)
    # We always need a clear line to work with
    clearLine(2)
    # Re-write line 2 with new value, with effect if requested
    LineVal[2] = string
    putLine(2, LineVal[2], effect)
    # Add an end-of-line pause if effects are enabled
    if effect:
        sleep_ms(100) # This feels comfortable

#
# Entire display manipulation
#

def blink(count):
    for i in range(0,count):
        display(False)
        sleep_ms(500)
        display(True)
        sleep_ms(500)

################################################################################
# Program Entry
################################################################################

if __name__ == "__main__":

    # Always do this, because the hardware probably wasn't power-cycled to trigger the POR
    resetLcd()

    # Set up the display how we'd like to work with it
    cmd('DISPLAY_ON')
    cmd('CURSOR_HOME')

    Lines = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    for text in Lines:
        pushLine(text, True)

    cmd('DISPLAY_CLEAR')
