#!/usr/bin/python

# Copyright (c) FIRST and other WPILib contributors.
# Open Source Software; you can modify and/or share it under the terms of
# the WPILib BSD license file in the root directory of this project.

# Based on https://github.com/REVrobotics/Color-Sensor-v3/blob/main/src/main/java/com/revrobotics/ColorSensorV3.java
#
# Copyright (c) 2019 REV Robotics
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of REV Robotics nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

###############################################################################
#
# Setting up the rPi:
# - ssh in (username pi, password raspberry), then:
#   - run "rw" to put the Pi into writable mode
#   - run "sudo systemctl enable pigpiod"
#   - run "sudo raspi-config", Interface Options, I2C, Yes, OR:
#     - edit /etc/modules, add "i2c-dev" line
#     - edit /boot/config.txt:
#       - uncomment "dtparam=i2c_arm=on" line
#
# The default hardware I2C bus is bus 1 on GPIO 2 (Data) and GPIO 3 (Clock).
# These pins include 1.8k pull-up resistors to 3.3V.
#
# It is possible to get up to 4 additional I2C busses (3, 4, 5, 6) via other GPIO pins.
# Note: you'll need to add external pull-ups to 3V3 on these GPIO pins.
# Alternatively, the Pi has support for external I2C mux devices hooked up to
# I2C bus 1, see i2c-mux in /boot/overlays/README.
#
# On the rPi 3b, software I2C must be used; add the following to /boot/config.txt:
#       dtoverlay=i2c-gpio,bus=6,i2c_gpio_sda=22,i2c_gpio_scl=23
#       dtoverlay=i2c-gpio,bus=5,i2c_gpio_sda=12,i2c_gpio_scl=13
#       dtoverlay=i2c-gpio,bus=4,i2c_gpio_sda=8,i2c_gpio_scl=9
#       dtoverlay=i2c-gpio,bus=3,i2c_gpio_sda=4,i2c_gpio_scl=5
# On the rPi 4, additional hardware busses are available; add to /boot/config.txt:
#       dtoverlay=i2c3
#       dtoverlay=i2c4
#       dtoverlay=i2c5
#       dtoverlay=i2c6
#
# This program shows how to operate a single device on bus 1 and two devices
# (one on bus 1 and one on bus 3). The multiple device code is commented out.
#
###############################################################################

import enum
import sys
import time
import os

SIMULATION = os.environ.get("SIMULATION", False)
SIMULATION = SIMULATION == "True"

if not SIMULATION:
    import pigpio
    pi = pigpio.pi()


class Color:

    def __init__(self, red: float, green: float, blue: float):
        self.red = red
        self.green = green
        self.blue = blue


class RawColor:

    def __init__(self, red: int, green: int, blue: int, ir: int):
        self.red = red
        self.green = green
        self.blue = blue
        self.ir = ir


class CIEColor:

    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z


class ColorSensorV3:
    """REV Robotics Color Sensor V3"""

    kAddress = 0x52
    kPartID = 0xC2

    def __init__(self, port: int):
        """
        Constructs a ColorSensor.

        port  The I2C port the color sensor is attached to
        """
        self.i2c = pi.i2c_open(port, self.kAddress)

        if not self._checkDeviceID():
            return

        self._initializeDevice()

        # Clear the reset flag
        self.hasReset()

    class Register(enum.IntEnum):
        kMainCtrl = 0x00
        kProximitySensorLED = 0x01
        kProximitySensorPulses = 0x02
        kProximitySensorRate = 0x03
        kLightSensorMeasurementRate = 0x04
        kLightSensorGain = 0x05
        kPartID = 0x06
        kMainStatus = 0x07
        kProximityData = 0x08
        kDataInfrared = 0x0A
        kDataGreen = 0x0D
        kDataBlue = 0x10
        kDataRed = 0x13

    class MainControl(enum.IntFlag):
        kRGBMode = 0x04  # If bit is set to 1, color channels are activated
        kLightSensorEnable = 0x02  # Enable light sensor
        kProximitySensorEnable = 0x01  # Proximity sensor active
        OFF = 0x00  # Nothing on

    class GainFactor(enum.IntEnum):
        kGain1x = 0x00
        kGain3x = 0x01
        kGain6x = 0x02
        kGain9x = 0x03
        kGain18x = 0x04

    class LEDCurrent(enum.IntEnum):
        kPulse2mA = 0x00
        kPulse5mA = 0x01
        kPulse10mA = 0x02
        kPulse25mA = 0x03
        kPulse50mA = 0x04
        kPulse75mA = 0x05
        kPulse100mA = 0x06  # default value
        kPulse125mA = 0x07

    class LEDPulseFrequency(enum.IntEnum):
        kFreq60kHz = 0x18  # default value
        kFreq70kHz = 0x40
        kFreq80kHz = 0x28
        kFreq90kHz = 0x30
        kFreq100kHz = 0x38

    class ProximitySensorResolution(enum.IntEnum):
        kProxRes8bit = 0x00
        kProxRes9bit = 0x08
        kProxRes10bit = 0x10
        kProxRes11bit = 0x18

    class ProximitySensorMeasurementRate(enum.IntEnum):
        kProxRate6ms = 0x01
        kProxRate12ms = 0x02
        kProxRate25ms = 0x03
        kProxRate50ms = 0x04
        kProxRate100ms = 0x05  # default value
        kProxRate200ms = 0x06
        kProxRate400ms = 0x07

    class ColorSensorResolution(enum.IntEnum):
        kColorSensorRes20bit = 0x00
        kColorSensorRes19bit = 0x10
        kColorSensorRes18bit = 0x20
        kColorSensorRes17bit = 0x30
        kColorSensorRes16bit = 0x40
        kColorSensorRes13bit = 0x50

    class ColorSensorMeasurementRate(enum.IntEnum):
        kColorRate25ms = 0
        kColorRate50ms = 1
        kColorRate100ms = 2
        kColorRate200ms = 3
        kColorRate500ms = 4
        kColorRate1000ms = 5
        kColorRate2000ms = 7

    def configureProximitySensorLED(
        self, freq: LEDPulseFrequency, curr: LEDCurrent, pulses: int
    ):
        """
        Configure the the IR LED used by the proximity sensor.

        These settings are only needed for advanced users, the defaults
        will work fine for most teams. Consult the APDS-9151 for more
        information on these configuration settings and how they will affect
        proximity sensor measurements.

        freq      The pulse modulation frequency for the proximity
                  sensor LED
        curr      The pulse current for the proximity sensor LED
        pulses    The number of pulses per measurement of the
                  proximity sensor LED (0-255)
        """
        self._write8(self.Register.kProximitySensorLED, freq | curr)
        self._write8(self.Register.kProximitySensorPulses, pulses)

    def configureProximitySensor(
        self, res: ProximitySensorResolution, rate: ProximitySensorMeasurementRate
    ):
        """
        Configure the proximity sensor.

        These settings are only needed for advanced users, the defaults
        will work fine for most teams. Consult the APDS-9151 for more
        information on these configuration settings and how they will affect
        proximity sensor measurements.

        res   Bit resolution output by the proximity sensor ADC.
        rate  Measurement rate of the proximity sensor
        """
        self._write8(self.Register.kProximitySensorRate, res | rate)

    def configureColorSensor(
        self,
        res: ColorSensorResolution,
        rate: ColorSensorMeasurementRate,
        gain: GainFactor,
    ):
        """
        Configure the color sensor.

        These settings are only needed for advanced users, the defaults
        will work fine for most teams. Consult the APDS-9151 for more
        information on these configuration settings and how they will affect
        color sensor measurements.

        res   Bit resolution output by the respective light sensor ADCs
        rate  Measurement rate of the light sensor
        gain  Gain factor applied to light sensor (color) outputs
        """
        self._write8(self.Register.kLightSensorMeasurementRate, res | rate)
        self._write8(self.Register.kLightSensorGain, gain)

    def getColor(self) -> Color:
        """
        Get the most likely color. Works best when within 2 inches and
        perpendicular to surface of interest.

        Returns the most likely color, including unknown if
        the minimum threshold is not met
        """
        r = self.getRed()
        g = self.getGreen()
        b = self.getBlue()
        mag = r + g + b
        return Color(r / mag, g / mag, b / mag)

    def getProximity(self):
        """
        Get the raw proximity value from the sensor ADC (11 bit). This value
        is largest when an object is close to the sensor and smallest when
        far away.

        Returns proximity measurement value, ranging from 0 to 2047
        """
        return self._read11BitRegister(self.Register.kProximityData)

    def getRawColor(self) -> RawColor:
        """
        Get the raw color values from their respective ADCs (20-bit).

        Returns Color containing red, green, blue and IR values
        """
        return RawColor(self.getRed(), self.getGreen(), self.getBlue(), self.getIR())

    def getRed(self) -> int:
        """
        Get the raw color value from the red ADC

        Returns Red ADC value
        """
        return self._read20BitRegister(self.Register.kDataRed)

    def getGreen(self) -> int:
        """
        Get the raw color value from the green ADC

        Returns Green ADC value
        """
        return self._read20BitRegister(self.Register.kDataGreen)

    def getBlue(self) -> int:
        """
        Get the raw color value from the blue ADC

        Returns Blue ADC value
        """
        return self._read20BitRegister(self.Register.kDataBlue)

    def getIR(self) -> int:
        """
        Get the raw color value from the IR ADC

        Returns IR ADC value
        """
        return self._read20BitRegister(self.Register.kDataInfrared)

    # This is a transformation matrix given by the chip
    # manufacturer to transform the raw RGB to CIE XYZ
    _Cmatrix = [
        0.048112847, 0.289453437, -0.084950826, -0.030754752, 0.339680186,
        -0.071569905, -0.093947499, 0.072838494, 0.34024948
    ]

    def getCIEColor(self) -> CIEColor:
        """
        Get the color converted to CIE XYZ color space using factory
        calibrated constants.

        https://en.wikipedia.org/wiki/CIE_1931_color_space

        Returns CIEColor value from sensor
        """
        raw = self.getRawColor()
        return CIEColor(
            self._Cmatrix[0] * raw.red
            + self._Cmatrix[1] * raw.green
            + self._Cmatrix[2] * raw.blue,
            self._Cmatrix[3] * raw.red
            + self._Cmatrix[4] * raw.green
            + self._Cmatrix[5] * raw.blue,
            self._Cmatrix[6] * raw.red
            + self._Cmatrix[7] * raw.green
            + self._Cmatrix[8] * raw.blue,
        )

    def hasReset(self) -> bool:
        """
        Indicates if the device reset. Based on the power on status flag in the
        status register. Per the datasheet:

        Part went through a power-up event, either because the part was turned
        on or because there was power supply voltage disturbance (default at
        first register read).

        This flag is self clearing

        Returns bool indicating if the device was reset
        """
        raw = pi.i2c_read_byte_data(self.i2c, self.Register.kMainStatus)

        return (raw & 0x20) != 0

    def _checkDeviceID(self) -> bool:
        raw = pi.i2c_read_byte_data(self.i2c, self.Register.kPartID)

        if self.kPartID != raw:
            print("Unknown device found with same I2C addres as REV color sensor")
            return False

        return True

    def _initializeDevice(self):
        self._write8(
            self.Register.kMainCtrl,
            self.MainControl.kRGBMode
            | self.MainControl.kLightSensorEnable
            | self.MainControl.kProximitySensorEnable,
        )

        self._write8(
            self.Register.kProximitySensorRate,
            self.ProximitySensorResolution.kProxRes11bit
            | self.ProximitySensorMeasurementRate.kProxRate100ms,
        )

        self._write8(self.Register.kProximitySensorPulses, 32)

    def _read11BitRegister(self, reg: Register) -> int:
        count, raw = pi.i2c_read_i2c_block_data(self.i2c, reg, 2)

        return ((raw[0] & 0xFF) | ((raw[1] & 0xFF) << 8)) & 0x7FF

    def _read20BitRegister(self, reg: Register) -> int:
        count, raw = pi.i2c_read_i2c_block_data(self.i2c, reg, 3)

        return (
            (raw[0] & 0xFF) | ((raw[1] & 0xFF) << 8) | ((raw[2] & 0xFF) << 16)
        ) & 0x03FFFF

    def _write8(self, reg: Register, data: int):
        pi.i2c_write_byte_data(self.i2c, reg, data)


configFile = "/boot/frc.json"
team = 3636
server = False


def parseError(str: str):
    """Report parse error."""
    print("config error in '" + configFile + "': " + str, file=sys.stderr)


def readConfig():
    """Read configuration file."""
    global team
    global server

    # parse file
    import json

    try:
        with open(configFile, "rt", encoding="utf-8") as f:
            j = json.load(f)
        with open(configFile, "rt", encoding="utf-8") as f:
            j = json.load(f)
    except OSError as err:
        print("could not open '{}': {}".format(configFile, err), file=sys.stderr)
        return False

    # top level must be an object
    if not isinstance(j, dict):
        parseError("must be JSON object")
        return False

    # team number
    try:
        team = j["team"]
    except KeyError:
        parseError("could not read team number")
        return False

    # ntmode (optional)
    if "ntmode" in j:
        str = j["ntmode"]
        if str.lower() == "client":
            server = False
        elif str.lower() == "server":
            server = True
        else:
            parseError("could not understand ntmode value '{}'".format(str))

    return True


def get_colors(sensor1, sensor2):
    rawcolor = sensor1.getRawColor()
    prox = sensor1.getProximity()
    colorEntry1.setDoubleArray(
        [rawcolor.red, rawcolor.green, rawcolor.blue, rawcolor.ir]
    )
    proxEntry1.setDouble(prox)

    r = rawcolor.red
    g = rawcolor.green
    b = rawcolor.blue

    mag = r + g + b
    r1 = r / mag
    g1 = g / mag
    b1 = b / mag

    rawcolor = sensor2.getRawColor()
    prox = sensor2.getProximity()
    colorEntry2.setDoubleArray(
        [rawcolor.red, rawcolor.green, rawcolor.blue, rawcolor.ir]
    )
    proxEntry2.setDouble(prox)

    r = rawcolor.red
    g = rawcolor.green
    b = rawcolor.blue
    mag = r + g + b
    r2 = r / mag
    g2 = g / mag
    b2 = b / mag

    return ((r1, g1, b1), (r2, g2, b2))


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        configFile = sys.argv[1]

    # read configuration
    if not readConfig() and not SIMULATION:
        sys.exit(1)
    

    # start NetworkTables
    from networktables import NetworkTablesInstance

    ntinst = NetworkTablesInstance.getDefault()
    if server:
        print("Setting up NetworkTables server")
        ntinst.startServer()
    else:
        print("Setting up NetworkTables client for team {}".format(team))
        ntinst.startClientTeam(team)
        ntinst.startDSClient()

    if not SIMULATION:
        sensor1 = ColorSensorV3(1)
        sensor2 = ColorSensorV3(0)

    colorEntry1 = ntinst.getEntry("/rawcolor1")
    proxEntry1 = ntinst.getEntry("/proximity1")

    colorEntry2 = ntinst.getEntry("/rawcolor2")
    proxEntry2 = ntinst.getEntry("/proximity2")
    didDetectLastR = (False, False)
    didDetectLastB = (False, False)
    # loop forever
    import time
    import pygame
    from pygame import mixer

    pygame.init()
    mixer.init()

    auto = False
    autoPauseActive = False
    endTime = time.time()
    matchRunning = False
    matchReady = True

    paused = False
    pausedTime = 0
    endTimeAtPause = 0

    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    redAutoScore = 0    
    blueAutoScore = 0
    redScore = 0
    blueScore = 0
    redPens = 0
    bluePens = 0
    font = pygame.font.SysFont("IBM Plex Mono", 500)
    timerFont = pygame.font.SysFont("IBM Plex Mono", 80)
    endGameFont = pygame.font.SysFont("IBM Plex Mono", 750)
    phaseFont = pygame.font.SysFont("IBM Plex Mono", 200)
    pygame.mouse.set_visible(False)
    run = True

    lastPhase = "Controllers Down"
    currentScreen = "none"
    blinkFrames = 0
    redScoreBlinkFrames = 0
    blueScoreBlinkFrames = 0

    while run:
        displayed_phase = ""
    
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    run = False
                elif event.key == pygame.K_c:
                    matchReady = True
                    matchRunning = False
                    redScore = 0
                    blueScore = 0
                    redPens = 0
                    bluePens = 0
                    redAutoScore = 0
                    blueAutoScore = 0
                    auto = False
                    autoPauseActive = False
                    paused = False
                elif event.key == pygame.K_b:
                    matchReady = False
                    auto = False
                    matchRunning = True
                    endTime = time.time() + 135
                    redScore = 0
                    blueScore = 0
                    redPens = 0
                    bluePens = 0
                    paused = False
                elif event.key == pygame.K_SPACE:
                    if not matchRunning:
                        matchReady = False
                        auto = True
                        matchRunning = True
                        endTime = time.time() + 15
                        redScore = 0
                        blueScore = 0
                        redPens = 0
                        bluePens = 0
                        redAutoScore = 0
                        blueAutoScore = 0
                        paused = False
                    else:
                        paused = not paused
                        if paused:
                            pausedTime = time.time()
                            endTimeAtPause = endTime
                    
                elif event.key == pygame.K_y:
                    blueScore = blueScore + 1
                    blueScoreBlinkFrames = 7
                elif event.key == pygame.K_t:
                    redScore = redScore + 1
                    redScoreBlinkFrames = 7
                elif event.key == pygame.K_h:
                    blueScore = blueScore - 1
                elif event.key == pygame.K_g:
                    redScore = redScore - 1
                elif event.key == pygame.K_i:
                    bluePens = bluePens + 1
                elif event.key == pygame.K_e:
                    redPens = redPens + 1
                elif event.key == pygame.K_k:
                    bluePens = bluePens - 1
                elif event.key == pygame.K_d:
                    redPens = redPens - 1
                elif event.key == pygame.K_u:
                    blueAutoScore = blueAutoScore + 2
                    blueScore = blueScore + 2
                    blueScoreBlinkFrames = 7
                elif event.key == pygame.K_r:
                    redAutoScore = redAutoScore + 2
                    redScore = redScore + 2
                    redScoreBlinkFrames = 7
                elif event.key == pygame.K_j:
                    blueAutoScore = blueAutoScore - 2
                    blueScore = blueScore - 2
                elif event.key == pygame.K_f:
                    redAutoScore = redAutoScore - 2
                    redScore = redScore - 2

            # if event.type == pygame.KEYLEFT:
            # if event.type == pygame.KEYRIGHT:

        if not paused:
            if endTime <= time.time() and auto:
                auto = False
                autoPauseActive = True
                endTime = time.time() + 5
            elif endTime <= time.time() and not auto:
                if autoPauseActive:
                    endTime = time.time() + 135
                    autoPauseActive = False
                else:
                    matchRunning = False
        else:
            endTime = endTimeAtPause + (time.time() - pausedTime)

        if not SIMULATION:

            # read sensor and send to NT
            ((r1, g1, b1), (r2, g2, b2)) = get_colors(sensor1, sensor2)

            if r1 > 0.45 and b1 < 0.3 and didDetectLastR == (False, False):
                # if matchRunning and not paused:
                if auto or autoPauseActive:
                    redScore = redScore + 2
                    redAutoScore = redAutoScore + 2
                else:
                    redScore = redScore + 1
                didDetectLastR = (True, didDetectLastR[0])
                redScoreBlinkFrames = 7
            elif r1 < 0.45:
                didDetectLastR = (False, didDetectLastR[0])

            if r2 < 0.4 and b2 > 0.4 and didDetectLastB == (False, False):
                # if matchRunning and not paused:
                if auto or autoPauseActive:
                    blueScore = blueScore + 2
                    blueAutoScore = blueAutoScore + 2
                else:
                    blueScore = blueScore + 1
                didDetectLastB = (True, didDetectLastB[0])
                blueScoreBlinkFrames = 7
            elif b2 < 0.4:
                didDetectLastB = (False, didDetectLastB[0])

        if matchReady:
            displayed_phase = "Controllers Down"
        elif autoPauseActive:
            displayed_phase = "Pick Up Your Controller!"
        elif auto:
            displayed_phase = "Auto"
        elif matchRunning:
            displayed_phase = "Drive Your Robot!"
        else:
            displayed_phase = "Controllers Down (Match Ended)!"

        if displayed_phase != lastPhase and not matchReady and displayed_phase != "Controllers Down (Match Ended)!" and displayed_phase != "Drive Your Robot!":
            blinkFrames = 25
            lastPhase = displayed_phase

        # if displayed_phase == "Controllers Down (Match Ended)!" and displayed_phase != lastPhase:
        #     mixer.music.load("end.mp3")
        #     mixer.music.play()

        if blinkFrames > 0:
            currentScreen = "blinky"
            blinkFrames = blinkFrames - 1
        else:
            currentScreen = "scores"

        screen.fill("black")
        if currentScreen == "scores":
            displayed_time = str(round(endTime - time.time()))
            if not matchRunning:
                displayed_time = "0"
            theFont = None
            endGame = round(endTime - time.time()) <= 10 and matchRunning and not auto
            if endGame:
                theFont = endGameFont
            else:
                theFont = timerFont
            if displayed_time == "0" and autoPauseActive:
                displayed_time = "Go!"
            timer_text = theFont.render(displayed_time, True, "white")
            timer_text_rect = timer_text.get_rect(center=(1920 / 2, 800))
            screen.blit(timer_text, timer_text_rect)
            
            if not endGame:
                current_phase_text = timerFont.render(displayed_phase, True, "white")
                current_phase_text_rect = current_phase_text.get_rect(center=(1920 / 2, 900))
                screen.blit(current_phase_text, current_phase_text_rect)

            if paused and not endGame:
                paused_text = timerFont.render("Paused", True, "white")
                paused_text_rect = paused_text.get_rect(center=(1920 / 2, 1000))
                screen.blit(paused_text, paused_text_rect)

            blue_auto_text = timerFont.render("Auto: " + str(blueAutoScore), True, "blue")
            blue_auto_text_rect = blue_auto_text.get_rect(center=(640, 250))
            screen.blit(blue_auto_text, blue_auto_text_rect)
            blue_pens_text = timerFont.render("Penalty: " + str(bluePens), True, "white")
            blue_pens_text_rect = blue_pens_text.get_rect(center=(640, 350))
            screen.blit(blue_pens_text, blue_pens_text_rect)
            red_auto_text = timerFont.render("Auto: " + str(redAutoScore), True, "red")
            red_auto_text_rect = red_auto_text.get_rect(center=(1920 - 640, 250))
            screen.blit(red_auto_text, red_auto_text_rect)
            red_pens_text = timerFont.render("Penalty: " + str(redPens), True, "white")
            red_pens_text_rect = red_pens_text.get_rect(center=(1920 - 640, 350))
            screen.blit(red_pens_text, red_pens_text_rect)

            winner_pos = (0, 0)
            winner_color = "white"
            if not matchRunning and not matchReady:
                if blueScore - bluePens > redScore - redPens:
                    winner_pos = (640, 100)
                    winner_color = "blue"
                elif redScore - redPens > blueScore - bluePens:
                    winner_pos = (1920 - 640, 100)
                    winner_color = "red"
                else:
                    winner_pos = (1920 / 2, 100)

                winner_text = timerFont.render("winner winner chicken dinner", True, winner_color)
                winner_text_rect = winner_text.get_rect(center=winner_pos)
                screen.blit(winner_text, winner_text_rect)


            blueScoreColor = "blue"
            redScoreColor = "red"   

            if blueScoreBlinkFrames > 0:
                # Make text flash in and out
                # if blueScoreBlinkFrames % 4 >= 2:
                blueScoreColor = "dodgerblue"
                # Draw circle to the left of the score
                pygame.draw.circle(screen, blueScoreColor, (640 - 300, 650), 50)
                blueScoreBlinkFrames = blueScoreBlinkFrames - 1


            if redScoreBlinkFrames > 0:
                # Make text flash in and out
                # if redScoreBlinkFrames % 4 >= 2:
                redScoreColor = "tomato"
                # Draw circle to the right of the score
                pygame.draw.circle(screen, redScoreColor, (1920 - 640 + 300, 650), 50)
                redScoreBlinkFrames = redScoreBlinkFrames - 1
                

            red_text = font.render(str(redScore), True, redScoreColor)
            red_text_rect = red_text.get_rect(center=(1920 - 640, 540))

            screen.blit(red_text, red_text_rect)

            blue_text = font.render(str(blueScore), True, blueScoreColor)
            blue_text_rect = red_text.get_rect(center=(640, 540))

            screen.blit(blue_text, blue_text_rect)

        elif currentScreen == "blinky":
            shown = displayed_phase
            if displayed_phase == "Auto":
                shown = "Press Your Auto Button!"
            elif displayed_phase == "Controllers Down (Match Ended)!":
                shown = "Controllers Down!"
            color = ""
            blinkyMagic = 1
            if displayed_phase == "Pick Up Your Controller!":
                blinkyMagic = 2
            if blinkFrames / 4 % 4 >= blinkyMagic:
                color = "white"
            else:
                if displayed_phase == "Pick Up Your Controller!":
                    color = "white"
                    shown = "Do Not Drive!"
                else: 
                    color = "black"
            phase_text = phaseFont.render(shown, True, color)
            phase_text_rect = phase_text.get_rect(center=(1920 / 2, 540))
            screen.blit(phase_text, phase_text_rect)

        # flush NT
        ntinst.flush()

        pygame.display.flip()

        # sleep before we poll again (max NT rate is 5 ms so sleep at least
        # that long)
        if SIMULATION:
            time.sleep(1 / 15)
        else:
            time.sleep(0.005)
