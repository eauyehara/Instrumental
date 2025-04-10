# -*- coding: utf-8 -*-
# Copyright 2023 Dodd Gray
"""
Driver module for HP 70000 spectrum analyzer.
Based on Nate's Tektronix scope driver
"""

import numpy as np
import pyvisa
from pint import UndefinedUnitError

from ... import Q_, u
from .. import VisaMixin
from . import Spectrometer

_INST_PARAMS = ['visa_address']
_INST_VISA_INFO = {
    'HPOSA': ('HEWLETT-PACKARD', ['70951B'])
}
# disp_visa_address = 'GPIB0::4::INSTR'
# osa_visa_address = 'GPIB0::23::INSTR'
# default_params = {'visa_address':osa_visa_address}

def _check_visa_support(visa_inst):
    id = visa_inst.query('ID?')
    if id=='HP70951B\n':
        return 'HPOSA'

class HPOSA(Spectrometer, VisaMixin):
    """
    A base class for HP 70000 series spectrum analyzers
    """
    def _initialize(self):
        self._rsrc.read_termination = '\n'  # Needed for stripping termination
        self._rsrc.timeout = 300
        self._rsrc.write_termination = ';'
        self.write('TDF P') # set the trace data format to be decimal numbers in parameter units

    def instrument_presets(self):
        self.write('IP')
        self.write('TDF P') # set the trace data format to be decimal numbers in parameter units

    def set_center_wavelength(self,cf):
        cf_nm = cf.to(u.nm).magnitude
        self.write('CF {:4.5f}NM'.format(cf_nm))

    def get_center_wavelength(self):
        cf = (float(self.query('CF?')) * u.m).to(u.nm)
        return cf

    def set_wavelength_span(self,sp):
        sp_nm = sp.to(u.nm).magnitude
        self.write('SP {:4.5f}NM'.format(sp_nm))

    def get_wavelength_span(self):
        sp = (float(self.query('SP?')) * u.m).to(u.nm)
        return sp

    def get_sweep_time(self):
        self._rsrc.timeout = 5000
        st = (float(self.query('ST?')) * u.s)
        return st

    def set_resolution_bandwidth(self,rb):
        rb_nm = rb.to(u.nm).magnitude
        self.write('RB {:4.5f}NM'.format(rb_nm))

    def get_resolution_bandwidth(self):
        rb = (float(self.query('RB?')) * u.m).to(u.nm)
        return rb

    def set_amplitude_units(self,au):
        if au==u.watt:
            self.write('AUNITS W')
        elif au==u.milliwatt:
            self.write('AUNITS MW')
        elif au=='dBm':
            self.write('AUNITS DBM')

    def get_amplitude_units(self):
        au_str = self.query('AUNITS?')
        if au_str=='W':
            au = u.watt
        elif au_str=='MW':
            au = u.milliwatt
        elif au_str=='DBM':
            au = u.dimensionless
        return au

    def set_sensitivity(self,sens):
        #sens = 10*np.log10(sens.to(u.milliwatt).magnitude)
        self.write('SENS {:3.3E}'.format(sens.to(self.get_amplitude_units()).magnitude))

    def set_log_scale(self,scale):
        ### scale
        self.write('LG {}DB'.format(scale))

    def set_linear_scale(self):
        self.write('LN')

    def set_reference_level(self,ref_level):
        ### scale
        if self.get_amplitude_units()==u.dimensionless:
            if ref_level.units==u.dimensionless:
                self.write('RL {:3.3E} DBM'.format(ref_level.magnitude))
            else:
                self.write('RL {:3.3E} DBM'.format(10*np.log10(ref_level.to(u.milliwatt).magnitude)))
        else:
            if ref_level.units==u.dimensionless:
                self.write('RL {:3.3E} mW'.format(10**(ref_level/10.0)))
            else:
                self.write('RL {:3.3E} mW'.format(ref_level.to(u.milliwatt).magnitude))

    def get_sensitivity(self):
        sens_dbm = float(self.query('SENS?'))
        sens = (10**(sens_dbm/10.0) * u.milliwatt).to(u.watt)
        return sens

    def get_spectrum(self,trace='A'):
        self._rsrc.timeout = 15000
        au = self.get_amplitude_units()
        wl_center = self.get_center_wavelength()
        wl_span = self.get_wavelength_span()
        self.write('TS;DONE?')
        # self.write('VIEW TR%s' % trace)
        amp = np.fromstring(self.query('TR'+trace+'?'),sep=',') * au
        wl_start = wl_center - wl_span / 2.0
        wl_stop = wl_center + wl_span / 2.0
        n_pts = len(amp)
        wl = Q_(np.linspace(wl_start.magnitude,wl_stop.magnitude,n_pts),wl_start.units)
        self._rsrc.timeout = 300
        self.write('CLRW TR%s' % trace)
        return wl, amp

    # def get_data(self, channel=1):
    #     """Retrieve a trace from the scope.
    #
    #     Pulls data from channel `channel` and returns it as a tuple ``(t,y)``
    #     of unitful arrays.
    #
    #     Parameters
    #     ----------
    #     channel : int, optional
    #         Channel number to pull trace from. Defaults to channel 1.
    #
    #     Returns
    #     -------
    #     t, y : pint.Quantity arrays
    #         Unitful arrays of data from the scope. ``t`` is in seconds, while
    #         ``y`` is in volts.
    #     """
    #     # inst = self.inst
    #     self._rsrc.timeout = 10000
    #
    #     self.write("data:source ch{}".format(channel))
    #     stop = int(self.query("wfmpre:nr_pt?"))  # Get source's number of points
    #     stop = 10000
    #     self.write("data:width 2")
    #     self.write("data:encdg RIBinary")
    #     self.write("data:start 1")
    #     self.write("data:stop {}".format(stop))
    #
    #     #inst.flow_control = 1  # Soft flagging (XON/XOFF flow control)
    #     tmo = self.timeout
    #     self.timeout = 10000
    #     self.write("curve?")
    #     self.read_termination = None
    #     self.end_input = pyvisa.constants.SerialTermination.none
    #     # TODO: Change this to be more efficient for huge datasets
    #     with self.ignore_warning(pyvisa.constants.VI_SUCCESS_MAX_CNT):
    #         s = self.visalib.read(self.session, 2)  # read first 2 bytes
    #         num_bytes = int(self.visalib.read(self.session, int(s[0][1]))[0])
    #         buf = ''
    #         while len(buf) < num_bytes:
    #             raw_bin, _ = self.visalib.read(self.session, num_bytes-len(buf))
    #             buf += raw_bin
    #             print(len(raw_bin))
    #     self.end_input = pyvisa.constants.SerialTermination.termination_char
    #     self.read_termination = '\n'
    #     self.read()  # Eat termination
    #     self.timeout = tmo
    #     raw_data_y = np.frombuffer(buf, dtype='>i2', count=int(num_bytes//2))
    #
    #     # Get scale and offset factors
    #     x_scale = float(self.query("wfmpre:xincr?"))
    #     y_scale = float(self.query("wfmpre:ymult?"))
    #     x_zero = float(self.query("wfmpre:xzero?"))
    #     y_zero = float(self.query("wfmpre:yzero?"))
    #     x_offset = float(self.query("wfmpre:pt_off?"))
    #     y_offset = float(self.query("wfmpre:yoff?"))
    #
    #     x_unit_str = self.query("wfmpre:xunit?")[1:-1]
    #     y_unit_str = self.query("wfmpre:yunit?")[1:-1]
    #
    #     unit_map = {
    #         'U': '',
    #         'Volts': 'V'
    #     }
    #
    #     x_unit_str = unit_map.get(x_unit_str, x_unit_str)
    #     try:
    #         x_unit = u.parse_units(x_unit_str)
    #     except UndefinedUnitError:
    #         x_unit = u.dimensionless
    #
    #     y_unit_str = unit_map.get(y_unit_str, y_unit_str)
    #     try:
    #         y_unit = u.parse_units(y_unit_str)
    #     except UndefinedUnitError:
    #         y_unit = u.dimensionless
    #
    #     raw_data_x = np.arange(1, stop+1)
    #
    #     data_x = Q_((raw_data_x - x_offset)*x_scale + x_zero, x_unit)
    #     data_y = Q_((raw_data_y - y_offset)*y_scale + y_zero, y_unit)
    #
    #     return data_x, data_y

    def read_measurement_stats(self, num):
        """
        Read the value and statistics of a measurement.

        Parameters
        ----------
        num : int
            Number of the measurement to read from, from 1-4

        Returns
        -------
        stats : dict
            Dictionary of measurement statistics. Includes value, mean, stddev,
            minimum, maximum, and nsamps.
        """
        prefix = 'measurement:meas{}'.format(num)

        if not self.are_measurement_stats_on():
            raise Exception("Measurement statistics are turned off, "
                            "please turn them on.")

        # Potential issue: If we query for all of these values in one command,
        # are they guaranteed to be taken from the same statistical set?
        # Perhaps we should stop_acquire(), then run_acquire()...
        keys = ['value', 'mean', 'stddev', 'minimum', 'maximum']
        res = self.inst.query(prefix+':value?;mean?;stddev?;minimum?;maximum?;units?').split(';')
        units = res.pop(-1).strip('"')
        stats = {k: Q_(rval+units) for k, rval in zip(keys, res)}

        num_samples = int(self.inst.query('measurement:statistics:weighting?'))
        stats['nsamps'] = num_samples
        return stats

    def read_measurement_value(self, num):
        """Read the value of a measurement.

        Parameters
        ----------
        num : int
            Number of the measurement to read from, from 1-4

        Returns
        -------
        value : pint.Quantity
            Value of the measurement
        """
        prefix = 'measurement:meas{}'.format(num)

        raw_value, raw_units = self.inst.query('{}:value?;units?'.format(prefix)).split(';')
        units = raw_units.strip('"')
        return Q_(raw_value+units)

    def set_math_function(self, expr):
        """Set the expression used by the MATH channel.

        Parameters
        ----------
        expr : str
            a string representing the MATH expression, using channel variables
            CH1, CH2, etc. eg. 'CH1/CH2+CH3'
        """
        self.inst.write("math:type advanced")
        self.inst.write('math:define "{}"'.format(expr))

    def get_math_function(self):
        return self.inst.query("math:define?").strip('"')

    def run_acquire(self):
        """Sets the acquire state to 'run'"""
        self.inst.write("acquire:state run")

    def stop_acquire(self):
        """Sets the acquire state to 'stop'"""
        self.inst.write("acquire:state stop")

    def are_measurement_stats_on(self):
        """Returns whether measurement statistics are currently enabled"""
        res = self.inst.query("measu:statistics:mode?")
        return res not in ['OFF', '0']

    def enable_measurement_stats(self, enable=True):
        """Enables measurement statistics.

        When enabled, measurement statistics are kept track of, including
        'mean', 'stddev', 'minimum', 'maximum', and 'nsamps'.

        Parameters
        ----------
        enable : bool
            Whether measurement statistics should be enabled
        """
        # For some reason, the DPO 4034 uses ALL instead of ON
        self.inst.write("measu:statistics:mode {}".format('ALL' if enable else 'OFF'))

    def disable_measurement_stats(self):
        """Disables measurement statistics"""
        self.enable_measurement_stats(False)

    def set_measurement_nsamps(self, nsamps):
        """Sets the number of samples used to compute measurements.

        Parameters
        ----------
        nsamps : int
            Number of samples used to compute measurements
        """
        self.inst.write("measu:stati:weighting {}".format(nsamps))

    def get_peak_info(self, peak_id=['HIP', 'NH']):
        """
        Find the peak of the spectra and returns the frequency and the amplitude in a list
        :param peak_id: Type of peak to look for.
                'CP': closest peak
                'CPIT': closest pit
                'HI': highest point on the trace
                'HIP': highest peak
                'MI': minimum peak (NOT the same as the minimum point!)
                'MIPIT': lowest pit
                'NH': next highest signal level detected
                'NHPIT': next highest pit
                'NL': next signal peak to the left
                'NLPIT': next signal pit to the left.
                'NM': next minimum peak
                'NMPIT: next lowest pit.
                'NR': next peak to the right
                'NRPIT': next pit to the right
        :return:
        """
        pk_wl = []
        pk_amp = []

        self._rsrc.timeout = 5000
        for pk in peak_id:
            self.write('TS;DONE?;')
            self.write('MK;')  # position a marker
            self.write('MKPK %s;' % pk)  # move the marker to the peak

            amp = self.query('MKA?;')
            wl = self.query('MKF?;')

            pk_wl.append(float(wl))
            pk_amp.append(float(amp))

        self._rsrc.timeout = 300

        return [pk_wl*u.m, Q_(pk_amp, 'dBm')]