"""
A demonstration of hd44780.py

Requires MicroPython on Raspberry Pi Pico
--
Copyright 2023 Kyle Botteon

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

from hd44780 import hardware_interface as hd44780

def main():

    pinout = hd44780.Pinout()
    pinout.D = [10, 11, 12, 13]
    pinout.E = 14
    pinout.RS = 15
    pinout.RWn = None

    lcd = hd44780(pinout)

    # Always do this, because the hardware probably wasn't power-cycled to trigger the POR
    lcd.reset()

    # Turn on the display and bring cursor home to start writing
    lcd.start()

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
        lcd.pushLine(text, True)

    lcd.clear()

if __name__ == "__main__":
    main()
