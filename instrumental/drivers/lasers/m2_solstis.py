# -*- coding: utf-8  -*-
# Copyright 2020 Nili Persits and Jaehwan Kim
"""
Driver for M2 Solstis Tunable Laser

This driver talks to ICE BLOC the controller for the Solstis laser through TCP/IP sockets

Usage Example:
    from instrumental.drivers.lasers.solstis import M2_Solstis
    # laser = M2_Solstis()
    laser.set_wavelength(wavelength=850.0)
    wavelength =  laser.get_wavelength()
    laser.close()
"""
from . import Laser
import socket
import json
from time import sleep
import sys
import numpy as np
from ... import Q_

_INST_CLASSES = ['M2_Solstis']


class M2_Solstis(Laser):
    """ A M2 Solstis tunable laser.

    _INST_PARAMS:
        host_address : Address to control computer
        port : Port
        client_ip : client ip setting in ICE BLOC
    """
    # _INST_PARAMS_ = ['host_address', 'port', 'client_ip']
    # _INST_PARAMS_ = []

    def _initialize(self):
        """ Initializes socket communications with laser controller and sends start_link command
        """
        # Internal parameters
        self.timeout = 1.0
        self.wavelength_tolerance = Q_(0.1,'nm')
        self.poll_timeout = 30
        host_address='localhost'
        port=9001
        client_ip='192.168.1.100'
        self.latest_reply = None

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.settimeout(self.timeout) # sets timeout
            # self.s.connect((self._paramset['host_address'], self._paramset['port']))
            self.s.connect((host_address, port))
        except:
            # print('M2_Solstis: cannot open socket connection to {}:{}'.format(self._paramset['host_address'], self._paramset['port']))
            print('M2_Solstis: cannot open socket connection to {}:{}'.format(host_address, port))
            print("Unexpected error:", sys.exc_info()[0])
            self.s = None
        else:
            # send start link command and parse return
            json_startlink = {
                'message': {
                    'transmission_id': [1],
                    'op': 'start_link',
                    'parameters': {
                        'ip_address': client_ip
                    }
                }
            }

            command_startlink = json.dumps(json_startlink)
            self.s.sendall(bytes(command_startlink,'utf-8'))

            json_reply = json.loads(self.s.recv(1024))
            if json_reply['message']['transmission_id'][0] == 1 and json_reply['message']['parameters']['status'] == 'ok':
                # print('M2_Solstis: successfully started link to {}:{} as {}'.format(self._paramset['host_address'], self._paramset['port'], self._paramset['client_id']))
                print('M2_Solstis: successfully started link to {}:{} as {}'.format(host_address, port, client_ip))
            else:
                # print('M2_Solstis: failed to start link to {}:{} as {}'.format(self._paramset['host_address'], self._paramset['port'], self._paramset['client_id']))
                print('M2_Solstis: failed to start link to {}:{} as {}'.format(host_address, port, client_ip))
                print('M2_Solstis: reply from controller {}'.format(json_reply))

                self.s.close()
                self.s = None

    def one_shot(self):
        """ Runs one-shot routine for beam alignment
        First moves the laser's center wavelength to 780 nm followed by one-shot command
        Returns
        -------
        status: str
            returns status of the one shot command
        """
        self.set_wavelength(wavelength = Q_(780, 'nm'))

        if self.s is not None:
            transID=97
            json_oneshot = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'beam_alignment',
                    'parameters': {
                        'mode': [4]
                    }
                }
            }
            self.s.sendall(bytes(json.dumps(json_oneshot),'utf-8'))
            sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply
            if json_reply['message']['parameters']['status'] == 0:
                print('M2_Solstis: one shot beam alignment successful')

                return 'Success'
            elif json_reply['message']['parameters']['status'] == 1:
                print('M2_Solstis: one shot beam alignment failed')

                return 'Failed'
            else:
                print('Gavin says things are fucked up, yo')

                return 'fubar'
        else:
            print('M2_Solstis: socket not connected')
            return 'Failed'

    def get_wavelength(self):
        """ Returns wavelength from wavemeter in nanometers

        Returns
        -------
        wavelength : Q_ class
            returns current measured wavelength if successful or Q_(0.0, 'nm') otherwise
        """

        wavelength =  Q_(0.0, 'nm')

        if self.s is not None:
            transID=99
            json_getwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'poll_wave_m'
                }
            }
            self.s.sendall(bytes(json.dumps(json_getwave),'utf-8'))
            sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            if (json_reply['message']['transmission_id'] == [transID]) and (json_reply['message']['parameters']['status'] in [[0], [2], [3]]):
                wavelength = Q_(json_reply['message']['parameters']['current_wavelength'][0], 'nm')
                print('M2_Solstis: Current wavelength from wavemeter is {}'.format(wavelength))

                if json_reply['message']['parameters']['status'] ==[0]:
                    print('M2_Solstis: idle')
                if json_reply['message']['parameters']['status'] ==[2]:
                    print('M2_Solstis: Tuning laser wavelength')
                elif json_reply['message']['parameters']['status'] ==[3]:
                    print('M2_Solstis: maintaining target wavelength at {}'.format(wavelength))

            else:
                print('M2_Solstis: failed poll wavelength')
                print('M2_Solstis: reply from controller {}'.format(json_reply))

                wavelength =  Q_(0.0, 'nm')
        else:
            print('M2_Solstis: socket not connected')
            wavelength =  Q_(0.0, 'nm')

        self.latest_reply = json_reply
        return wavelength

    def set_wavelength(self, wavelength):
        """ Sends set wavelength command and checks reply

        Parameters
        ----------
        wavelength : Q_ class
            target wavelength

        Returns
        -------
        error : int or str
            Zero is returned if wavelength was set correctly.
            1 if not within tolerance after poll timeout.
            Otherwise, error string returned by the laser is returned.
        """
        if self.s is None:
            print('M2_Solstis: socket not connected')
            return Q_(0.0, 'nm')
        else:
            transID=91
            json_setwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'set_wave_m',
                    'parameters': {
                        'wavelength': [wavelength.to('nm').magnitude]
                    }
                }
            }

            self.s.sendall(bytes(json.dumps(json_setwave),'utf-8'))
            sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply
            if json_reply['message']['transmission_id'] == [transID] and json_reply['message']['parameters']['status'] == [0]:
                print('M2_Solstis: started tuning to {}'.format(wavelength))

                for i in range(self.poll_timeout):
                    current_wavelength = self.get_wavelength()
                    if self.latest_reply['message']['parameters']['status'] in [[3]]:
                        print('M2_Solstis: finished tuning to {}'.format(current_wavelength))
                        return 0

                print('M2_Solstis: current wavelength {}'.format(current_wavelength))
                return 1
            else:
                print('M2_Solstis: failed poll wavelength')
                print('M2_Solstis: reply from controller {}'.format(json_reply))

                return json_reply

    def close(self):
        """
        Closes socket connection to the laser.
        """
        if self.s is not None:
            self.s.close()
