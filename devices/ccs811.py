#!/bin/env python3
# -*- coding: utf-8 -*-
# devices/ccs811.py

import logging, time
from pyi2c import I2CDevice, getBit


class CCS811:
    """
    CCS811 -- the board name is CJMCU-811 --
    can measure equivalent Total Volatile Organic Compund (eTVOC) in ppb (0~32768)
    and equivalent CO2 (eCO2) in ppm(400~29206).

    Address is 0x5a, or 0x5b
    Firmware version is 2.0.0

    CAUTION
    1. DO NOT USE single transaction such as bus.write_byte, it does not work.
       Use bus.i2c_rdwr( i2c_msg ), instead.
    2. The value is 'equivalent'. eCO2 is calculated from eTVOC. So, ignore eCO2 value.
    3. Accuracy N/A. The value does not math with other sensors. See
       https://www.jaredwolff.com/finding-the-best-tvoc-sensor-ccs811-vs-bme680-vs-sgp30/
    """
    def __init__(self, bus_n=0, addr=0x5a):
        self._i2cdevice = I2CDevice(bus_n, addr)
        # commands
        self._APP_START_ADDR = 0xf4 # from boot to application mode
        self._MEAS_MODE_ADDR = 0x01
        # 0: write, 001: every second, 0: nINT interrupt disable, 0: operate normally, 00: nothing
        self._MEAS_MODE_CMD = 0b0001_0000 # 0x10
        self._RESULT_ADDR = 0x02
        self._ENV_DATA = 0x05 # Temperature and Humidity data can be written to enable compensatio
        self._SW_RESET = 0xff
        logging.info('CCS811 created.')

    def initialize(self):
        # Start application mode
        self._i2cdevice.write(self._APP_START_ADDR)
        time.sleep(.1) # .1 s
        logging.info('CCS811 initialized.')

        # Set measurement mode
        self._i2cdevice.write([self._MEAS_MODE_ADDR, self._MEAS_MODE_CMD])
        time.sleep(.1) # .1 s
        logging.info('CCS811 set to measurement mode.')

    def softReset(self):
        data = [
                self._SW_RESET, 0x11, 0xE5, 0x72, 0x8A
                ]
        self._i2cdevice.write(data)
        time.sleep(.1) # .1 s
        logging.info('CCS811 did soft reset and return to boot mode.')

    def writeEnvironmentData(self, humidity, temperature):
        if humidity > 0 and temperature > -25:
            write_data = [
                    self._ENV_DATA,
                    int( (humidity*2**9)/(2**8) ),
                    int( (humidity*2**9)%(2**8) ),
                    int( ((temperature+25)*2**9)/(2**8) ),
                    int( ((temperature+25)*2**9)%(2**8) ),
                    ]
            self._i2cdevice.write(write_data)

    # Return True when there is no problem
    def interpretStatus(self, status, error_id):
        is_ok = False
        if not status & 2**0 == 0:
            logging.warning('CCS811 has error')
            if not error_id & 2**0 == 0:
                logging.warning(' -- WRITE_REG_INVALID.')
            elif not error_id & 2**1 == 0:
                logging.warning(' -- READ_REG_INVALID.')
            elif not error_id & 2**2 == 0:
                logging.warning(' -- MEASMODE_INVALID.')
            elif not error_id & 2**3 == 0:
                logging.warning(' -- MAX_RESISTANCE. The sensor resistance measurement has reached or exceeded the maximum range.')
            elif not error_id & 2**4 == 0:
                logging.warning(' -- HEATER_FAULT. The Heater current in the CCS811 is not in range')
            elif not error_id & 2**5 == 0:
                logging.warning(' -- HEATER_SUPPLY. The Heater voltage is not being applied correctly')
            self.softReset()
            self.initialize()
        elif status & 2**3 == 0:
            logging.info('CCS811 has no new data')
        elif status & 2**4 == 0:
            logging.info('CCS811 did not load valid application firmware')
        elif status & 2**7 == 0:
            logging.info('CCS811 is not in application mode')
        else:
            is_ok = True
        return is_ok

    def getECO2ETVOC(self):
        # Select result register address
        # and read 8 bytes data rapidly
        read_data = self._i2cdevice.writeread(self._RESULT_ADDR, 8)

        # Prepare varibles
        eCO2 = TVOC = -1

        # Check i2c status code is success
        if self._i2cdevice.status_code.value == 0:

            # Treat status
            status = read_data[4]
            error_id = read_data[5]
            if self.interpretStatus(status, error_id):
                # Fill data
                eCO2 = (read_data[0] << 8) + read_data[1] # from 400 ppm to 29206 ppm
                TVOC = (read_data[2] << 8) + read_data[3] # from 0 ppb to 32768 ppb
                current = read_data[6] & 0b1111_1100
                raw_adc = (read_data[6] & 0b0000_0011) + read_data[7]

                # Check value
                if (TVOC < 0 or 32768 < TVOC):
                    logging.warning('CCS811 eCO2 value is strange.')
                    eCO2 = TVOC = -1

        return eCO2, TVOC


# Test main
def main():
    logging.basicConfig(
            format='%(asctime)s %(levelname)s %(message)s',
            level=logging.DEBUG
            )
    ccs811 = CCS811()
    ccs811.initialize()
    eCO2, TVOC = ccs811.getECO2TVOC()
    logging.info('eCO2: {0} ppm, TVOC: {1} ppb'.format(eCO2, TVOC))


if __name__ == "__main__":
    # execute only if run as a script
    main()
