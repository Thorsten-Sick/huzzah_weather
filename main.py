import ntptime
from machine import Pin, I2C
import machine
import ssd1306
import network
import secrets
import utime
import urequests
import dht
import neopixel
import esp

# TODO MQTT
# TODO extension: MQTT currently seems to not support HTTPS on ESP/Python. Fix
# TODO (optional) Servo for pointer to basic states
# TODO Harden against changes in OpenWeather format

# Configs
timeoffset = 1   # Offset in hours to London
CITYID = "2849802"  # Openweathermap city ID

# Hardware config
PINDHT = 2  # Pin for DHT 22 data
PINOLEDSCL = 5  # Pin for display SCL
PINOLEDSDA = 4  # Pin for display SDA
PINNEOPIXEL = 14  # Pin for neo pixel
PINDOOR = 12      # Pin for door sensor

# Colors for Neo pixel
RED = (100, 0, 0)       # Forecast: Will be raining and door is open
GREEN = (0, 100, 0)     # Forecast: No rain and warm. Good for biking
BLUE = (0, 0, 100)      #
BLACK = (0, 0, 0)       # switch it off


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

        self.weatherdata = None

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

    def getForecast(self):
        """Get forecast from OpenWeatherMap online service."""

        count = 3   # Number of items, reduce because: memory
        url = "http://api.openweathermap.org/data/2.5/forecast?id={0}&cnt={1}&units=metric&APPID={2}".format(CITYID, count, secrets.OPENWEATHERMAPKEY)
        r = urequests.get(url)
        if r.status_code == 200:
            self.weatherdata = r.json()
        else:
            print("Error getting weather map")

    def getRain(self):
        """Read weather data to check if it will rain."""
        res = []
        if self.weatherdata:
            for i in self.weatherdata["list"]:
                try:
                    res.append(i["rain"]["3h"])
                except:
                    print("No rain data for this time slot")
        return res

    def getSnow(self):
        """Read weather data to check if it will be snowing."""
        res = []
        if self.weatherdata:
            for i in self.weatherdata["list"]:
                try:
                    res.append(i["snow"]["3h"])
                except:
                    print("No snow data for this time slot")
        return res

    def getTemp(self):
        """Read weather data to check temp."""
        res = []
        if self.weatherdata:
            for i in self.weatherdata["list"]:
                res.append(i["main"]["temp"])
        return res



class WeatherStation():
    """Main weather station class."""

    def __init__(self):
        """Init the weather station."""

        # We do not want to sleep, wall socket powered...
        esp.sleep_type(esp.SLEEP_NONE)
        # SLEEP_MODEM is also an option, but prevent it from re-loading data...

        self.display = Display()
        self.net = Network()
        self.dht = dht.DHT22(machine.Pin(PINDHT))

        # Neopixel
        self.np = neopixel.NeoPixel(Pin(PINNEOPIXEL), 1)

        self.door = machine.Pin(PINDOOR, machine.Pin.IN, machine.Pin.PULL_UP)

        self.net.getForecast()
        #print(self.net.getRain())
        #print(self.net.getTemp())

        # Initial display
        self.updateDisplay()

        # Timer to periodically update display
        self.tim = machine.Timer(1)
        self.tim.init(period=60000, mode=machine.Timer.PERIODIC,
                      callback=lambda t: self.updateDisplay())

        # Forecast update
        self.tim = machine.Timer(2)
        self.tim.init(period=60000*3, mode=machine.Timer.PERIODIC,
                      callback=lambda t: self.net.getForecast())

    def doorOpen(self):
        return self.door.value()

    def setNP(self, color):
        """Set neo pixel."""

        self.np[0] = color
        self.np.write()

    def measure(self):
        """Collect different measurements."""
        self.dht.measure()

    def updateDisplay(self):
        """Update the display."""
        self.measure()
        self.display.clear()
        comment = self.logic()
        # Time
        tme = self.net.gettime()
        self.display.showText("{0}:{1}".format(tme[3], tme[4]), 0)
        # Temp/Hum
        self.display.showText("Innen: {0}:{1}".format(self.dht.temperature(),
                                                      self.dht.humidity()), 1)
        # Forecast
        temp = self.net.getTemp()
        self.display.showText("Temp: {0}:{1}".format(min(temp), max(temp)), 2)

        # Rain
        rain = self.net.getRain()
        if len(rain):
            mrain = max(rain)
        else:
            mrain = 0
        self.display.showText("Rain(max): {0}".format(mrain), 3)

        # Snow
        snow = self.net.getSnow()
        if len(snow):
            msnow = max(snow)
        else:
            msnow = 0
        self.display.showText("Snow(max): {0}".format(msnow), 4)

        # Comment
        self.display.showText(comment, 5)

    def logic(self):
        """Use logic to help the user."""
        try:
            rain = max(self.net.getRain())
        except ValueError:
            rain = 0
        try:
            temp = max(self.net.getTemp())
        except ValueError:
            temp = 0

        hum = self.dht.humidity()

        rt = 0.001   # rain threshold
        res = ""

        if rain < rt and temp > 10:
            # Good for biking
            self.setNP(GREEN)
            res = "biking"
        elif rain > rt and self.doorOpen():
            self.setNP(RED)
            res = "HODOR"
        elif hum < 40 or hum > 60:
            self.setNP(BLUE)
            res = "Humidity !"
        else:
            self.setNP(BLACK)
            res = ""
        return res

# TODO: Get if door is opened

# TODO: MQTT communication

ws = WeatherStation()
