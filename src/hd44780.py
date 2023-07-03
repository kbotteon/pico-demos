"""
Hardware management for devices based on the HD44780 LCD driver

Requires MicroPython on Raspberry Pi Pico
--
Copyright 2022 Kyle Botteon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from machine import Pin as Gpio
from utime import sleep_us, sleep_ms
from collections import namedtuple
# No `dataclasses`, `typing`, or `enum` in MicroPython

class HardwareInterface:
    """
    Hardware wrapper object for HD44780
    """

    class DramRange:
        """
        The address space that display character array exists within
        Configured for a 2x16 display; see datasheet if that's not what you have
        """
        # Line 1
        L1_START = 0x00
        L1_END = 0x27
        # Line 2
        L2_START = 0x40
        L2_END = 0x67

    class Pinout:
        """
        Pi Pico GPIO number (not hardware pin number)

        Define D0-D7 to use 8-bit mode, or D4-D7 to use 4-bit mode

        You might be able to get away without R/W' by tieing it to ground,
        leaving write mode always enabled
        """
        def __init__(self):
            self.D = list()
            self.E = None
            self.TS = None
            self.RWn = None

    class Mode:
        """
        The LCD IC always starts in 8-bit mode and must be commanded into 4
        pin mode if desired
        """
        DATA_8 = 1
        DATA_4 = 2

    # LCD opcodes and execution times
    # See datasheet p. 24
    # key: opcode, duration [us]
    cmd_pair = namedtuple('cmd_pair', 'opcode duration')
    COMMANDS = {
        # Not a command, but a default wait time when needed
        'DEFAULT': cmd_pair(0x00, 37),
        'DISPLAY_ON': cmd_pair(0x0E, 37),
        'DISPLAY_OFF': cmd_pair(0x08, 37),
        # Duration for this one isn't actually specified, so assume a similar
        # duration to Return Home because they're similar operations
        'DISPLAY_CLEAR': cmd_pair(0x01, 1500),
        'CURSOR_HOME': cmd_pair(0x02, 1520),
        'MODE_AUTOINC': cmd_pair(0x06, 4),
        # 8-bit mode, 2 lines, 5x8 display
        'FUNCSEL_8BIT': cmd_pair(0x38, 37),
        # 4-bit mode, 2 lines, 5x8 display
        'FUNCSEL_4BIT': cmd_pair(0x28, 37),
        'DDRAM_SET': cmd_pair(0x80, 37)
    }

    def __init__(self, pinout: Pinout):
        """
        Set up the hardware based on `pinout` configuration
        """

        self.pinout = pinout

        # Hardware starts in 8-pin mode by default
        self.mode = self.Mode.DATA_8

        # This is shared among functions to determine whether a GPIO direction swap
        # should be performed; that takes time, so avoid when possible
        self.output_enabled = False

        # Local storage for whatever is presently on screen
        # Start with 16 blank spaces, and pad it so indices [1] and [2] line up with the
        # physical line numbers
        self.line_val = [ "", " "*16, " "*16 ]

        # This will soon be populated with hardware control objects
        self.hw_pin = self.Pinout()

        # Configure data pins
        if self.pinout.RWn == None:
            self.hw_pin.D = [Gpio(pin_idx, Gpio.OUT, value=0) for pin_idx in self.pinout.D]
            self.output_enabled = True
        else:
            self.hw_pin.D = [Gpio(pin_idx, Gpio.IN, value=0) for pin_idx in self.pinout.D]
            self.hw_pin.RWn = Gpio(self.pinout.RWn, Gpio.OUT, value=1)
            self.output_enabled = False

        # Configure enable pin
        self.hw_pin.E = Gpio(self.pinout.E, Gpio.OUT, value=1)

        # Configure
        self.hw_pin.RS = Gpio(self.pinout.RS, Gpio.OUT, value=1)

    def reset(self):
        """
        The chip has a POR, but it can also be re-initialized with:
            1. Set RS = 0, R/W' = 0
            2. Write 0x30
            3. Wait 4.1 ms
            4. Write 0x30
            5. Wait 100 us
            6. Write 0x38 (N = 1, F = 0)
            7. Write 0x0F
            8. Write 0x01
            9. Write 0x07 (I/D = 1, S = 1)
        """

        if len(self.hw_pin.D) == 8:
            self.write(0x30, True, 4100)
            self.write(0x30, True, 100)
            self.write(0x30, True, 100)
            # This can only be set during reset sequence or immediately after power on
            self.do_cmd('FUNCSEL_8BIT')
            self.mode = self.Mode.DATA_8

        elif len(self.hw_pin.D) == 4:
            # Borrow 8-bit mode in send() to do the unique 4-bit reset sequence; see p. 46
            self.write(0x3, True, 4100)
            self.write(0x3, True, 100)
            self.write(0x2, True, 100)
            self.write(0x2, True, 100)
            # This can only be set during reset sequence or immediately after power on
            self.do_cmd('FUNCSEL_4BIT')
            # Now we're in 4-bit mode; say tell send() it should use that mode
            self.mode = self.Mode.DATA_4

        else:
            raise Exception("Generate PinCtl with a valid number of control pins: 4 or 8")

        # These default settings can be changed later
        self.do_cmd('DISPLAY_OFF')
        self.do_cmd('DISPLAY_CLEAR')
        self.do_cmd('MODE_AUTOINC')

    def start(self):
        self.do_cmd('DISPLAY_ON')
        self.do_cmd('CURSOR_HOME')

    def clear(self):
        self.do_cmd('DISPLAY_CLEAR')

    def en_gpio_out(self, enable):
        """
        Direction swapping for bidirectional bus
        """
        if(enable):
            self.output_enabled = True
            # Ensure the bus won't be driven in contention, if we control it
            if self.hw_pin.RWn != None:
                self.hw_pin.RWn.low() # LCD write mode expects Pico to drive bus
            # Reconfigure the data GPIO as outputs
            self.hw_pin.D = [Gpio(pin_idx, Gpio.OUT, value=0) for pin_idx in self.pinout.D]
        else:
            self.output_enabled = False
            # Ensure the bus won't be driven in contention, if we control it
            if self.hw_pin.RWn != None:
                self.hw_pin.RWn.high() # LCD read mode will drive bus
            # Reconfigure the data GPIO as inputs
            self.hw_pin.D = [Gpio(pin_idx, Gpio.IN, Gpio.PULL_DOWN) for pin_idx in self.pinout.D]

    def do_cmd(self, name):
        """
        Make it a little easier to send commands by wrapping the lookup of
        opcode and duration
        """
        params = self.COMMANDS.get(name)
        self.write(params.opcode, True, params.duration)

    def read(self):
        """
        See datasheet p.33, 4 bit operation
        """

        # If there is not pin to toggle R/W mode, this isn't going to work, otherwise
        # enter READ mode
        if self.pinout.RWn == None:
            raise Exception("Can't read without a RWn pin")

        # See if the GPIO outputs are enabled, and disable those if so
        if self.output_enabled:
            self.en_gpio_out(False)

        # Must do this AFTER setting the GPIO to inputs so we don't drive in contention
        self.hw_pin.RWn.high()

        # Generate the control signals for a read
        self.hw_pin.RS.low() # If this is high, it reads the data register instead of 'busy' and 'addr'
        self.hw_pin.E.high()
        sleep_us(1) # Enable to data output delay and minimum intra-enable cycle time

        # Data is valid by now, read it and drop enable for the next caller to get updated value
        data = 0
        for elem in self.hw_pin.D:
            data = data | (elem.value() << self.hw_pin.D.index(elem))
        self.hw_pin.E.low()
        sleep_us(1)

        # Return 4 or 8 bits depending on mode; do NOT automatically do an 8-bit read
        # in 4-bit mode, because the user does not need that to check the BUSY flag
        return data

    def write(self, char, is_cmd, exe_time):
        """
        Write to HD44780

        See datasheet p.58 for timing diagrams

        Steps:
          1. Assert RS and R/W'
          2. Wait 40ns
          3. Assert Enable
          4. Assert data bits
          5. Wait 230ns (min enable pulse is longer than data setup)
          6. Deassert Enable. Data is latched
          7. Hold data 10ns
          8. Wait until 1us has elapsed since step 3

        FIXME: Datasheet says we must check the busy flag before proceeding
        """
        # Verify busy is not asserted
        if self.pinout.RWn != None:
            val = self.read()
            # TODO: If the busy flag is actually set...which it should never be
            # Must do this BEFORE enabling GPIO outputs so we don't drive in contention
            self.hw_pin.RWn.low()

        # If the outputs are not enabled, switch modes
        if not self.output_enabled:
            self.en_gpio_out(True)

        # R/S = 0 for command or 1 for data
        if is_cmd:
            self.hw_pin.RS.low()
        else:
            self.hw_pin.RS.high()

        # E falling edge will latch data, and the datasheet doesn't specify
        # setup time, so we guess it's safe to drive this high now
        self.hw_pin.E.high()

        if self.mode == self.Mode.DATA_8:
            # For each Pin bit, see if it should be asserted or not and do so
            for elem in self.hw_pin.D:
                if (char >> self.hw_pin.D.index(elem)) & 0x1 == 0x1:
                    elem.high()
                else:
                    elem.low()

        elif self.mode == self.Mode.DATA_4:
            CMD_HI = (char >> 4) & 0xF
            CMD_LO = char & 0xF
            # Send the upper 4 bits of command
            for elem in self.hw_pin.D:
                if (CMD_HI >> self.hw_pin.D.index(elem)) & 0x1 == 0x1:
                    elem.high()
                else:
                    elem.low()
            sleep_us(1) # Min E pulse and addr setup time
            self.hw_pin.E.low()
            sleep_us(1) # Intra-enable pulse time
            # Now send the lower 4 bits of command
            self.hw_pin.E.high()
            for elem in self.hw_pin.D:
                if (CMD_LO >> self.hw_pin.D.index(elem)) & 0x1 == 0x1:
                    elem.high()
                else:
                    elem.low()

        else:
            raise Exception("Valid mode options are 8BIT and 4BIT")

        # 230 ns minimum enable pulse time
        sleep_us(1)
        self.hw_pin.E.low()

        # Exit write mode
        if self.pinout.RWn != None:
            self.hw_pin.RWn.low()

        # 1 us minimum intra-enable pulse time, plus command execution time
        sleep_us(1 + exe_time)

    def put_char(self, char):
        """
        Write a character to the cursor location
        """
        binVal = ord(char)
        self.write(binVal, False, self.COMMANDS.get("DEFAULT")[0])

    def set_line(self, lineNo):
        """
        Select a display line for an operation
        """
        valid = {1, 2}
        if lineNo not in valid:
            raise ValueError("Valid range is 1:2")

        # Generate commands
        # D7 = 1
        # D6:0 = ADDR
        if lineNo == 1:
            DRAM_ADDR_CMD = self.COMMANDS.get("DDRAM_SET").opcode | self.DramRange.L1_START
        else:
            DRAM_ADDR_CMD = self.COMMANDS.get("DDRAM_SET").opcode | self.DramRange.L2_START

        self.write(DRAM_ADDR_CMD, True, self.COMMANDS.get("DDRAM_SET").duration)

    def put_line(self, lineNo, string, typingEn):
        """
        Write a string to a line on the display
        """
        self.set_line(lineNo)
        self.line_val[lineNo] = string
        # We can sequentially enter data immediately after a set_line()
        for char in string:
            self.put_char(char)
            if typingEn:
                sleep_ms(110) # Seems to be a nice speed for typing effect

    def clear_lin(self, lineNo):
        """
        Clear an entire line on the display
        """
        self.put_line(lineNo, " "*16, False)

    def push_line(self, string, typingEn):
        """
        Move line 2 to line 1, then write a new line 2
        """
        self.clear_lin(1)
        self.line_val[1] = self.line_val[2]
        self.put_line(1, self.line_val[1], False)
        # We always need a clear line to work with
        self.clear_lin(2)
        # Re-write line 2 with new value, with effect if requested
        self.line_val[2] = string
        self.put_line(2, self.line_val[2], typingEn)
        # Add an end-of-line pause if effects are enabled
        if typingEn:
            sleep_ms(100) # This feels comfortable

    def blink(self, count):
        for i in range(0,count):
            self.display(False)
            sleep_ms(500)
            self.display(True)
            sleep_ms(500)
