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
