import numpy as np
import pyvisa
import time
import re

from instrumental.drivers.powersupplies import PowerSupply
from instrumental.drivers import VisaMixin
from instrumental.drivers import ParamSet
from instrumental import Q_, u

# GPIB_ADDR = "GPIB0::29::INSTR"  # GPIB adress
DEFAULT_CURRENT_COMPLIANCE = 0.1 * u.A  # Default current compliance in A
DEFAULT_VOLTAGE_COMPLIANCE = 5 * u.A  # Default current compliance in V

def list_instruments():
    """Get a list of all power supplies currently attached"""
    paramsets = []
    search_string = "GPIB?*"
    rm = pyvisa.ResourceManager()
    raw_spec_list = rm.list_resources(search_string)

    for spec in raw_spec_list:
        try:
            inst = rm.open_resource(spec, read_termination='\n', write_termination='\n')
            idn = inst.query("*IDN?")
            manufacturer, model, serial, version = idn.rstrip().split(',', 4)
            if re.match(' Model 2635A', model):
                paramsets.append(ParamSet(Keithley, visa_address=spec, manufacturer=manufacturer, serial=serial, model=model, version=version))
        except pyvisa.errors.VisaIOError as vio:
            # Ignore unknown serial devices
            pass

    return paramsets

class Keithley(PowerSupply, VisaMixin):
    """
    Code for controlling Keithley2635A through GPIB
    """
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = {
        'Keithley': ('Keithley Instruments Inc.', [' Model 2635A'])
    }

    def _initialize(self,current_compliance=DEFAULT_CURRENT_COMPLIANCE,
                 voltage_compliance=DEFAULT_VOLTAGE_COMPLIANCE):
        """
        Initializes the instrument
        :return:
        """
        self._rsrc.read_termination = '\n'  # Needed for stripping termination
        self.cur_compliance = current_compliance
        self.volt_compliance = voltage_compliance
        self.is_on = 0
        self.mode = 'VOLTS'  # 'VOLTS' or 'AMPS'
        print('Opening connnection to Keithley source meter')

    def turn_on(self):
        """
        Turns the source on
        :return:
        """
        self.write("smua.source.output = smua.OUTPUT_ON")
        self.is_on = 1

    def turn_off(self):
        """
        Turns the source off
        :return:
        """
        self.write("smua.source.output = smua.OUTPUT_OFF")
        self.is_on = 0

    def set_func(self, mode):
        """
        :param mode: Either VOLT or CURR
        :return:
        """
        if not (mode == 'VOLTS' or mode == 'AMPS'):
            print('Source meter mode not correct. NO action taken')
            return

        self.write('smua.source.func = smua.OUTPUT_DC%s' %mode)  # set voltage
        self.mode = mode

    def set_voltage_compliance(self, v_comp):
        self.write('smua.source.limitv = %.4E' % v_comp.to(u.V).m)
        self.write('smua.measure.rangev = %.4E' % v_comp.to(u.V).m)
        self.volt_compliance = v_comp

    def set_current_compliance(self, i_comp):
        self.write('smua.source.limiti = %.4E' % i_comp.to(u.A).m)
        # self.write('smua.measure.rangei = %.4E' % i_comp.to(u.A).m)
        self.cur_compliance = i_comp

    def set_voltage(self, voltage):
        """
        Sets the specified voltage
        :param voltage:
        :return:
        """

        if not (self.mode == 'VOLTS'):
            self.turn_off()
            self.set_func('VOLTS')
            time.sleep(0.1)

        if not self.is_on:
            self.turn_on()

        self.write("smua.source.levelv = %.4E" % voltage.to(u.V).m)

    def set_current(self, current):
        """
        Sets the specified current
        :param current:
        :return:
        """

        if not (self.mode == 'AMPS'):
            self.turn_off()
            self.set_func('AMPS')
            time.sleep(0.1)

        if not self.is_on:
            self.turn_on()

        self.write("smua.source.leveli = %.4E" % current.to(u.A).m)

    def init_function(self):
        """
        Initializes the source meter
        """
        # self.write("reset()")
        # self.write('waitcomplete()')
        # Clear buffers
        self.write('format.data = format.ASCII')
        self.write('errorqueue.clear()')
        self.write('smua.nvbuffer1.clear()')
        self.write('waitcomplete()')

        self.set_func(self.mode)
        self.set_current_compliance(self.cur_compliance)
        self.set_voltage_compliance(self.volt_compliance)
        # Set longest integration time
        # self.write('smua.measure.nplc = 25')
        # self.set_measurement_interval(1)

    def measure_current(self):
        self.write('current1=smua.measure.i()')
        self.write('waitcomplete()')
        time.sleep(0.1)
        return float(self.query('print(current1)'))*u.A

    def measure_voltage(self):
        self.write('voltage1=smua.measure.v()')
        self.write('waitcomplete()')
        time.sleep(0.1)
        return float(self.query('print(voltage1)'))*u.V

    def take_IV(self, start_v, stop_v, num_v):
        """
        Takes an IV curve
        :return: A two column matrix, where the first column is voltage
        and the second is current
        """

        print('Starting IV measurement')
        sys.stdout.flush()

        measurements = np.zeros((num_v, 2), float)
        row = 0

        for v in np.linspace(start_v.to(u.V).m, stop_v.to(u.V).m, num_v):
            self.set_voltage(v)
            self.write('waitcomplete()')
            meas_current = self.measure_current()
            measurements[row, 0] = v * u.V
            measurements[row, 1] = meas_current * u.A
            print(
                'Set Voltage: %.4f mV ; Measured Current: %.4E mA' %
                (v * 1000, meas_current * 1000))
            sys.stdout.flush()
            row = row + 1

        return measurements

    def set_voltage_range(self, v_range):
        # Current in V
        self.write('smua.source.rangev= %.4E' % v_range.to(u.V).m)

    def set_current_range(self, i_range):
        # Current in Amps
        self.write('smua.source.rangei= %.4E' % i_range.to(u.A).m)

    def set_measurement_delay(self, time):
        self.write("smua.measure.delay = %.4E" % time.to(u.s).m)

    def set_measurement_interval(self, time):
        # Sets the measurement interval (in seconds)
        self.write('smua.measure.interval=%.4E' % time.to(u.s).m)

    def set_measurement_integration(self, nplc):
        # Sets the integration time in nplc units. 1 nplc is one period of the frequency of the AC power
        # So for 60 Hz, 1 NPLC = 17 ms. Has to be between 1 and 25
        if nplc > 25:
            print('Specified integration NPLC is more than the max. Setting to max.')
            nplc = 25
        if nplc < 1:
            print('Specified integration NPLC is smaller than the min. Setting to min.')
            nplc = 1
        self.write('smua.measure.nplc = %d' % nplc)

    def set_filter(self, enable=True, type='repeat_average', count=10):
        # Configures the digital filter that can be used to reduce readout
        # noise.

        # If enable = True, it turns on the digital filtering.
        # There are 3 different types:
        # - repeat_average: makes 'count' measurements and takes the average
        # - moving_average: takes the moving average of 'count' measurements
        # - median: takes the median of 'count measurements
        # Count: the number of measurements neede for one reading. Has to be
        # between 1 and 100

        if type == 'repeat_average':
            type_str = 'FILTER_REPEAT_AVG'
        elif type == 'moving_average':
            type_str = 'FILTER_MOVING_AVG'
        elif type == 'median':
            type_str = 'FILTER_MEDIAN'

        self.write('smua.measure.filter.type = smua.%s' % type_str)

        if count > 100:
            print('Specified filter count is more than the max. Setting to max.')
            count = 100
        if count < 1:
            print('Specified filter count is smaller than the min. Setting to min.')
            count = 1

        self.write('smua.measure.filter.count = %d' % count)

        if enable:
            self.write('smua.measure.filter.enable = smua.FILTER_ON')
        else:
            self.write('smua.measure.filter.enable = smua.FILTER_OFF')

    def linear_volt_sweep(self, volt_list, settling_time, num_points):
        """
        Take a linear voltage sweep with the following parameters
        :param volt_list: string of format '{V1, V2, V3,...}' [V]
        :param settling_time: float [s]
        :param num_points: integer
        """
        self.write('SweepVListMeasureI(smua, %s, %f, %d)' % (volt_list.to(u.V).m, settling_time.to(u.s).m, num_points))

    def close(self):
        print('Disconnecting Keithley source meter')
        # self.turn_off()
        self._rsrc.control_ren(False)
