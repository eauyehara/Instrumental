# -*- coding: utf-8 -*-
# Copyright 2020 Nate Bogdanowicz, Dodd Gray
"""
Driver module for Ibsen spectrometers.
"""
import numpy as np
from time import sleep
from enum import Enum
from . import Spectrometer
from .. import VisaMixin, SCPI_Facet
from ... import u, Q_

_INST_PARAMS_ = ['visa_address']
# _INST_VISA_INFO_ = {
#     'Eagle': ('JETI_PIC_VERSA',['']),
# }

def _check_visa_support(visa_rsrc):
    rt0 = visa_rsrc.read_termination
    wt0 = visa_rsrc.write_termination
    br0 = visa_rsrc.baud_rate
    visa_rsrc.read_termination = visa_rsrc.CR
    visa_rsrc.write_termination = visa_rsrc.CR
    visa_rsrc.baud_rate = 921600
    try:
        idn = visa_rsrc.query('*IDN?')
        if idn=="JETI_PIC_VERSA":
            return "Eagle"
        else:
            visa_rsrc.read_termination = rt0
            visa_rsrc.write_termination = wt0
            visa_rsrc.baud_rate = br0
            return None
    except:
        visa_rsrc.read_termination = rt0
        visa_rsrc.write_termination = wt0
        visa_rsrc.baud_rate = br0
        return None

# def _convert_enum(enum_type):
#     """Check if arg is an instance or key of enum_type, and return that enum
#     Strings are converted to lowercase first, so enum fields must be lowercase.
#     """
#     def convert(arg):
#         if isinstance(arg, enum_type):
#             return arg
#         try:
#             return enum_type[arg.lower()]
#         except (KeyError, AttributeError):
#             raise ValueError("{} is not a valid {} enum".format(arg, enum_type.__name__))
#     return convert


# class TriggerSource(Enum):
#     bus = 'BUS'
#     immediate = 'IMMMEDIATE'
#     external = 'EXT'
#     key = 'KEY'
#     timer = 'TIMER'
#     manual = 'MAN'
#


class Eagle(Spectrometer, VisaMixin):
    _INST_PARAMS_ = ['visa_address']
    # _INST_VISA_INFO_ = ('JETI_PIC_VERSA')

    def _initialize(self): #used in instrumental instead of __init__()
        self._rsrc.read_termination = self._rsrc.CR
        self._rsrc.write_termination = self._rsrc.CR
        self._rsrc.baud_rate = 921600
        self.spec_number = int(self.query('*PARA:SPNUM?').split()[-1])
        self.n_pixels = int(self.query('*PARA:PIX?').split()[-1])
        self.fit_params = [float(self.query(f'*PARA:FIT{j}?').split()[-1]) for j in range(5)] # quintic polynomial fit for wavelength vs pixel number
        self.wl = np.polyval(self.fit_params[::-1],np.arange(self.n_pixels)) # calculate wavelength array for this spectrometer
        self.serial_number = int(self.query('*PARA:SERN?').split()[-1])
        self.sensor = int(self.query('*PARA:SENS?').split()[-1])
        self.adc_res = int(self.query('*PARA:ADCR?').split()[-1])

    t_int = SCPI_Facet('*CONF:TINT', convert=int, units='ms')
    n_ave = SCPI_Facet('*CONF:AVE', convert=int, units='ms')

    def spectrum(self,t_int=10*u.ms):
        self._rsrc.write(f'*MEAsure {int(t_int.to(u.ms).m)} 1 2')
        sleep(t_int.to(u.second).m + 0.05)
        #counts = np.array([int(val) for val in self._rsrc.read().split()[1:]]) #original code, messes up for integration times > 5s
        raw_data = self._rsrc.read().split()
        data1 = raw_data[0][2:] #1st data point format gets messed up for integration times > 5s, process separately
        data_list = raw_data[1:]
        if data1 != '':
            data_list.insert(0, data1)
        counts = np.array([int(val) for val in data_list])
        return counts
        
    def spectrum_raw(self,t_int=10*u.ms):
        self._rsrc.write(f'*MEAsure {int(t_int.to(u.ms).m)} 1 2')
        sleep(t_int.to(u.second).m + 0.05)
        counts_raw = self._rsrc.read_raw()
        return counts_raw