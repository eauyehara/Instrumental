import sys
import logging as log
from time import sleep
import operator
import clr
import numpy as np
from . import Motion
# from ...util import to_str
from .. import ParamSet

clr.AddReference("System.Collections")
clr.AddReference("System.Linq")
from System.Collections.Generic import List #analysis:ignore
import System.Collections.Generic #analysis:ignore
from System import String, Decimal #analysis:ignore
import System.Linq #analysis:ignore
import System #analysis:ignore

sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.GenericPiezoCLI")
clr.AddReference("Thorlabs.MotionControl.Benchtop.PiezoCLI")
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI #analysis:ignore
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceNotReadyException #analysis:ignore
import Thorlabs.MotionControl.GenericPiezoCLI.Piezo as Piezo #analysis:ignore
from Thorlabs.MotionControl.Benchtop.PiezoCLI import BenchtopPiezo #analysis:ignore



def list_instruments():
    DeviceManagerCLI.BuildDeviceList()
    device_list = DeviceManagerCLI.GetDeviceList(BenchtopPiezo.DevicePrefix71)
    return [ParamSet(BPC203, serial=serial_str)
            for serial_str in device_list
            if serial_str]

class BPC203(Motion):
    """
    Main class for the BPC203 3 channel Benchtop Piezo Controller. Wraps the
    .NET base class from Thorlabs providing channel by channel control.
    Attributes and methods:
    attribute serial -- stores the serial number of the physical instrument
    attribute axis_chan_mapping -- stores the direction (x, y or z) which
        each channel of the controller addresses
    attribute isconnected -- boolean representing the state of the connection
        to the physical instrument
    attribute controller -- controller instance (from Thorlabs .NET dll)
    attributes xchannel, ychannel and zchannel -- channel instances
        (from Thorlabs .NET dll)
    attributes xmaxTravel, ymaxTravel, zmaxTravel -- max travel of each channel
    method __init__(self, axis_chan_mappign) --
    method __enter__(self) -- special class, see doc
    method connect(self) -- initializes the physical instrument
    """
    _INST_PARAMS_ = ['serial']

    def _initialize(self, axis_chan_mapping={'x': 1, 'y': 2, 'z': 3}):  #used in instrumental instead of __init__()
        """
        Method creating a BPC203 instance and setting up the connection to the
        device with serial number serial.
        """
        DeviceManagerCLI.BuildDeviceList()
        self.serial = self._paramset['serial']
        # self.deviceID = deviceID
        self.isconnected = False
        self.axis_chan_mapping = axis_chan_mapping
        self.controller = BenchtopPiezo.CreateBenchtopPiezo(self.serial)
        self.xmaxTravel = None
        self.ymaxTravel = None
        self.zmaxTravel = None

        for attrname in ("xchannel", "ychannel", "zchannel"):
            setattr(self, attrname, None)

    def __enter__(self):
        return self

    def __get_chan(self, axis):
        """
        Internal method returning the channel corresponding to axis
        """
        attrname = axis + "channel"
        channel = getattr(self, attrname)
        return(channel)

    def connect(self):
        """
        Method initializing the physical instrument, first the main controller
        unit and then each channel, which is linked to the corresponding axis
        as defined in self.axis_chan_mapping
        """
        print("Connecting to BPC203:")
        print("\t- connecting to controller %s -->" % self.serial, end="")
        self.controller.Connect(self.serial)
        self.isconnected = self.controller.IsConnected
        print(" done" if self.controller.IsConnected else "failed")
        for axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            attrname = axis + "channel"
            maxTravelname = axis + "maxTravel"
            print("\t- connecting channel %d (%s axis) -->" % (channelno, axis), end="")
            setattr(self, attrname, self.controller.GetChannel(channelno))

            channel = getattr(self, attrname)
            if not channel.IsSettingsInitialized():
                try:
                    channel.WaitForSettingsInitialized(5000)
                except:
                    raise
            channel.StartPolling(100)
            channel.EnableDevice()
            print(" done" if channel.IsConnected else "failed")
            setattr(self, maxTravelname, Decimal.ToDouble(channel.GetMaxTravel()))
        print("\n")

    def identify(self, axis):
        """
        Method identifying the channel corresponding to axis by making the
        controller blink.
        """
        if axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            print("Identifying BPC203 channel %d (%s axis) -->" % (channelno, axis), end="")
            channel = self.__get_chan(axis)
            channel.IdentifyDevice()
            sleep(5)
            print(" done")
        else:
            print("Cannot identify BPC203 channel (axis invalid)")
        print("\n")

    def set_close_loop(self, yes):
        """
        Method setting all channels to closed loop or open loop control mode
        """
        print("Setting control mode to %s loop" % "closed" if yes else "open")
        mode = Piezo.PiezoControlModeTypes.CloseLoop if yes else Piezo.PiezoControlModeTypes.OpenLoop
        print(mode)
        for axis in ("x", "y", "z"):
            channel = self.__get_chan(axis)
            channel.SetPositionControlMode(mode)

    def zero(self, axis="all"):
        """
        Method performing a Set Zero operation on all channels or on a single
        one
        """
        print("Performing Set Zero:")
        if axis == "all":
            for ax in ("x", "y", "z"):
                self.__zero_axis(ax)
            sleep(25) #if try talking to stage without 25s sleep after calling zero(), will not behave properly but won't give error
            print(" done")
        elif axis in ("x", "y", "z"):
            self.__zero_axis(axis)
            sleep(25)
            print(" done")
        else:
            print("\t- axis invalid)")


    def center(self, axis="XY"):
        """
        Method for moving all (default) or single axis to its piezo center position
        """
        if axis == "XY":
            print("Centering XY axes:")
            self.set_position(x=self.xmaxTravel/2, y=self.ymaxTravel/2, z=0)
        elif axis in ("x", "y", "z"):
            print("Centering %s axis" % axis)
            attrname = axis + "maxTravel"
            maxTravel = getattr(self, attrname)
            self.__set_axis_position(axis, maxTravel/2)
        else:
            print("\t- axis invalid)")


    def __zero_axis(self, axis):
        """
        Internal method performing a Set Zero operation on a single channel
        """
        if axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            print("\t- zeroing channel %d (%s axis) -->" % (channelno, axis))
            channel = self.__get_chan(axis)
            channel.SetZero()
            # print(" done")
        else:
            print("\t- axis invalid)")

    def set_position(self, x=None, y=None, z=None):  # define
        """
        Method setting the position in um if the channel is in
        Closed Loop mode
        """
        print("Setting Position:", flush=True)
        pos = {"x": x, "y": y, "z": z}
        for axis, pos in pos.items():
            if pos is None:
                pass
            else:
                self.__set_axis_position(axis, pos)

    def __set_axis_position(self, axis, pos):  # define
        """
        Internal method setting the position in um if the channel is in
        Closed Loop mode
        """
        if axis in ("x", "y", "z"):
            print("\t- moving %s axis piezo to %f um -->" % (axis, pos), end="")
            channel = self.__get_chan(axis)
            channel.SetPosition(Decimal(pos))
            print(" done")
        else:
            print("\t- axis invalid")

    def jog_to_position(self, stepSize=0.5, x=None, y=None, z=None):
        """
        Set position at a gentler speed (to prevent oscillations) by stepping by stepSize to specified position
        """
        pos = {"x": x, "y": y, "z": z}
        for axis, pos in pos.items():
            attrname = axis + "maxTravel"
            maxTravel = getattr(self, attrname)
            #Jog closer to final destination
            if pos is None:
                pass
            elif pos > maxTravel:
                print("\t- Invalid position - out of range")
            else:
                print("\t- Jogging %s axis piezo to %f um -->" % (axis, pos))
                init_pos = self.__get_axis_position(axis)
                sleep(0.3)
                travel_dist = pos-init_pos
                numSteps = int(np.floor(np.absolute(travel_dist)/stepSize))
                for i in range(numSteps):
                    if travel_dist > 0:
                        self.jog_axis(axis, stepSize, "Increase")
                    elif travel_dist < 0:
                        self.jog_axis(axis, stepSize, "Decrease")
                    sleep(0.3) #Position setting accumulates error without wait - error with 0.3s tolerable
                #final position set
                if self.__get_axis_position(axis) is not pos:
                    self.__set_axis_position(axis, pos)

    def jog_axis(self, axis, stepSize, direction):
        """
        Jogs along axis in specified direction by stepSize in um (closed-loop)
        direction is "Increase" or "Decrease"
        """
        if direction == "Increase":
            step = stepSize
        elif direction == "Decrease":
            step = -stepSize

        if axis in ("x", "y", "z"):
            init_pos = self.__get_axis_position(axis)
            self.__set_axis_position(axis, init_pos + step)
        else:
            raise ValueError("\t= axis invalid")

    def get_position(self):
        """
        Method getting the position in um (closed-loop)
        """
        pos = []
        for axis in ("x","y","z"):
            channel = self.__get_chan(axis)
            pos.append(Decimal.ToDouble(channel.GetPosition()))
        return pos

    def __get_axis_position(self, axis):
        """
        Internal method for retrieving axis position of single axis in closed loop mode
        """
        if axis in ("x", "y", "z"):
            channel = self.__get_chan(axis)
            pos = Decimal.ToDouble(channel.GetPosition())
        else:
            print("\t- axis invalid)")
        return pos

    def close(self):
        """
        Method for shutting down the connection to the physical instrument
        cleanly. The polling of the connected channels is stopped and the
        controller is disconnected.
        """
        print("Shutting BPC203 down:")
        if self.controller.IsConnected:
            for axis in ("x", "y", "z"):
                channelno = self.axis_chan_mapping[axis]
                print("\t- disconnecting channel %d (%s axis) -->" % (channelno, axis), end="")
                channel = self.__get_chan(axis)
                channel.StopPolling()
                channel.DisableDevice()
                print(" done")
            print("\t- disconnecting controller %s -->" % self.serial, end="")
            self.controller.Disconnect()
            print(" done")
        print("\t- done\n")


if __name__ == "__main__":
    # only reads accurate position every other time program run - weirdness with threading? test with ipython instead
    print("\n")
    # deviceID = "71829423"
    stage = BPC203()
    stage.connect()
    stage.set_close_loop(True)
    b = stage.get_position()
    print(b)
    # stage.set_position(b[0]+10)
    stage.center("all")
    # stage.zero("all")
    sleep(0.2)

    b = stage.get_position()
    print(b)
    sleep(5)
    # print(stage.get_position())

    del stage