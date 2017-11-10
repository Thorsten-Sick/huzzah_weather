import ntptime
from machine import Pin, I2C
import machine
import ssd1306
import network
import secrets
import utime
import urequests
import dht

# Configs
timeoffset = 1   # Offset in hours to London

# Hardware config
PINDHT = 2  # Pin for DHT 22 data
PINOLEDSCL = 5  # Pin for display SCL
PINOLEDSDA = 4  # Pin for display SDA


class Display():
    """SSD1306 based OLED display, 128x64).

    Ok with 6 lines of text
    """

    def __init__(self, inittext="Weather Central"):
        """Init the display."""
        self.inittext = inittext
        self.i2c = I2C(scl=Pin(PINOLEDSCL), sda=Pin(PINOLEDSDA), freq=100000)
        self.lcd = ssd1306.SSD1306_I2C(128, 64, self.i2c)
        self.lcd.text(self.inittext, 0, 0)
        self.lineWidth = 10
        self.lcd.show()

    def showText(self, text, line):
        """Show text at a give line.

        @text: Text to display
        @line: Line to display it at. 0-5 is ok for this display
        """
        self.lcd.text(text, 0, self.lineWidth*line)
        self.lcd.show()

    def clear(self, show=False):
        """Clear the display.

        @show: Set to directly update
        """
        self.lcd.fill(0)
        if show:
            self.lcd.show()


class Network():
    """Network and network data handling class."""

    def __init__(self):
        """Init the network."""
        self.sta_if = network.WLAN(network.STA_IF)
        self.sta_if.active(True)
        self.sta_if.connect(secrets.SSID, secrets.WIFIPWD)
        for i in range(0, 20):
            if self.sta_if.isconnected():
                self.settime()
                break
            print("Waiting for connection " + str(i))
            utime.sleep(1)
        # TODO: Opportunistic re-tra to connect

    def settime(self):
        """Set the time using NTP."""
        try:
            ntptime.settime()
        except OSError:
            pass  # timeout possible

    def gettime(self):
        """Get the time."""
        (y, m, d, h, m, s, foo, bar) = utime.localtime()
        return (y, m, d, h+timeoffset, m, s, foo, bar)

    def isconnected(self):
        """Check if the network is connected."""
        return self.sta_if.isconnected()


class WeatherStation():
    """Main weather station class."""

    def __init__(self):
        """Init the weather station."""
        self.display = Display()
        self.net = Network()
        self.dht = dht.DHT22(machine.Pin(PINDHT))

        # Initial display
        self.updateDisplay()

        # Timer to periodically update display
        self.tim = machine.Timer(1)
        self.tim.init(period=60000, mode=machine.Timer.PERIODIC,
                      callback=lambda t: self.updateDisplay())

    def measure(self):
        """Collect different measurements."""
        self.dht.measure()

    def updateDisplay(self):
        """Update the display."""
        self.measure()
        self.display.clear()
        # Time
        tme = self.net.gettime()
        self.display.showText("{0}:{1}".format(tme[3], tme[4]), 2)
        # Temp/Hum
        self.display.showText("Innen: {0}:{1}".format(self.dht.temperature(),
                                                      self.dht.humidity()), 3)


# TODO: Get weather forecast

# TODO: Get if door is opened

# TODO: MQTT communication

ws = WeatherStation()
