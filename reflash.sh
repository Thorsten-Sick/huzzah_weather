#!/bin/bash
esptool.py --port /dev/ttyUSB0 --baud 460800 write_flash --flash_size=detect 0 ../esp8266_firmware/esp8266-20171101-v1.9.3.bin
