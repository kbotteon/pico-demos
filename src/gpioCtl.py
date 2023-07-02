"""
A MicroPython helper to control Pi Pico GPIO

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

from machine import Pin as Pico_Pin

def config(dirStr):

    valid = {"IN", "OUT"}
    if dirStr not in valid:
        raise Exception("Valid directions are {IN, OUT}")

    # Pins are the **GP** number, not the pin number
    #   GP23 is the internal power save pin
    #   GP24 is the internal VBUS sense
    #   GP25 is LED
    #   GP29 is the internal pin used for ADC
    validPins = [i for i in list(range(0,22+1)) + list(range(26,28+1))]

    # Need a Pin object to control each pin individually
    if dirStr == "OUT":
        pinCtl = [Pico_Pin(pinNo, Pico_Pin.OUT) for pinNo in validPins]
    else:
        pinCtl = [Pico_Pin(pinNo, Pico_Pin.IN) for pinNo in validPins]

    return pinCtl

def setAll(level):

    pinCtl = config("OUT")

    valid = {0, 1}
    if level not in valid:
        raise ValueError("GPIO can only be 0 or 1")

    # For each Pin bit, see it low
    for elem in pinCtl:
        if level == 1:
            elem.high()
        else:
            elem.low()

def outDrive(enabled):

    pinCtl = config("IN")
