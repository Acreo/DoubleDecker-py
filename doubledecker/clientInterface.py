# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals
from builtins import str
from future import standard_library
standard_library.install_aliases()
from future.utils import with_metaclass
__license__ = """
  Copyright (c) 2015 Pontus Sköldström, Bertrand Pechenot

  This file is part of libdd, the DoubleDecker hierarchical
  messaging system DoubleDecker is free software; you can
  redistribute it and/or modify it under the terms of the GNU Lesser
  General Public License (LGPL) version 2.1 as published by the Free
  Software Foundation.

  As a special exception, the Authors give you permission to link this
  library with independent modules to produce an executable,
  regardless of the license terms of these independent modules, and to
  copy and distribute the resulting executable under terms of your
  choice, provided that you also meet, for each linked independent
  module, the terms and conditions of the license of that module. An
  independent module is a module which is not derived from or based on
  this library.  If you modify this library, you must extend this
  exception to your version of the library.  DoubleDecker is
  distributed in the hope that it will be useful, but WITHOUT ANY
  WARRANTY; without even the implied warranty of MERCHANTABILITY or
  FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
  License for more details.  You should have received a copy of the
  GNU Lesser General Public License along with this program.  If not,
  see <http://www.gnu.org/licenses/>.
"""

__author__ = 'Bertrand Pechenot'
__email__ = 'berpec@acreo.se'

import logging
import sys
import abc

import zmq
import zmq.eventloop.ioloop
import zmq.eventloop.zmqstream

from . import proto as DD


class Client(with_metaclass(abc.ABCMeta)):
    E_REGFAIL = DD.E_REGFAIL
    E_NODST = DD.E_NODST
    E_VERSION = DD.E_VERSION
    def __init__(self, name, dealerurl, customer):
        self._ctx = zmq.Context()
        self._IOLoop = zmq.eventloop.ioloop.IOLoop.instance()
        self._dealerurl = ''
        self._dealer = self._ctx.socket(zmq.DEALER)
        self._dealer.setsockopt(zmq.LINGER, 1000)
        self._state = DD.S_UNREG
        self._timeout = 0
        self._pubsub = False
        self._sublist = list()
        self._customer = ''
        self._pubkey = ''
        self._privkey = ''
        self._hash = ''
        self._cookie = ''
        self._safe = True
        if isinstance(name, str):
            name = name.encode()
        if isinstance(dealerurl, str):
            dealerurl = dealerurl.encode()
        if isinstance(customer, str):
            customer = customer.encode()

        self._name = name
        self._customer = customer
        self._customer_name = '.'.join([customer.decode(), name.decode()])  # e.g.: A.client1
        self._customer_name = self._customer_name.encode('utf8')

        self._dealerurl = dealerurl
        self._dealer.connect(self._dealerurl)
        self._stream = zmq.eventloop.zmqstream.ZMQStream(self._dealer, self._IOLoop)
        self._stream.on_recv(self._on_message)

        self._register_loop = zmq.eventloop.ioloop.PeriodicCallback(self._ask_registration, 1000)
        self._register_loop.start()
        logging.debug('Trying to register')

        self._heartbeat_loop = zmq.eventloop.ioloop.PeriodicCallback(self._heartbeat, 1500)

        logging.debug("Configured: name = %s, Dealer = %s, Customer = %s",
                      name.decode('utf8'),
                      dealerurl,
                      customer.decode('utf8'))

    def start(self):
        try:
            self._IOLoop.start()
        except KeyboardInterrupt:
            if self._state != DD.S_EXIT:
                self.shutdown()
            raise

    @abc.abstractmethod
    def on_pub(self, src, topic, msg):
        """ callback for published messages """
        pass

    @abc.abstractmethod
    def on_data(self, src, msg):
        """ callback for point to point messages """
        pass

    @abc.abstractmethod
    def on_reg(self):
        """ callback at registration"""
        pass

    @abc.abstractmethod
    def on_discon(self):
        """ callback at disconection """
        pass

    @abc.abstractmethod
    def on_error(self, code, msg):
        """ callback for error messages"""
        pass

    @abc.abstractmethod
    def subscribe(self, topic, scope):
        pass

    @abc.abstractmethod
    def unsubscribe(self, topic, scope):
        pass

    @abc.abstractmethod
    def publish(self, topic, message):
        pass

    @abc.abstractmethod
    def publish_public(self, topic, message):
        pass

    @abc.abstractmethod
    def sendmsg(self, dst, msg):
        pass

    def shutdown(self):
        logging.info('Shutting down')
        if self._state == DD.S_REGISTERED:
            for topic in self._sublist:
                logging.debug('Unsubscribing from %s', str(topic))
                self._dealer.send_multipart([DD.bPROTO_VERSION, DD.bCMD_UNSUB, topic.encode()])

            if self._safe:
                logging.debug('Unregistering from broker, safe')
                self._send(DD.bCMD_UNREG, [self._cookie, self._customer, self._name])
            else:
                logging.debug('Unregistering from broker')
                self._send(DD.bCMD_UNREG)
        else:
            logging.debug('Stopping register loop')
            self._register_loop.stop()
        self._state = DD.S_EXIT
        logging.debug('Stopping heartbeat loop')
        self._heartbeat_loop.stop()
        logging.debug('Closing stream')
        self._stream.close()
        logging.debug('Stopping IOloop')
        self._IOLoop.stop()
        logging.debug('Closing socket')
        self._dealer.close()
        logging.debug('Terminating context')
        self._ctx.term()
        logging.debug('Calling sys.exit')

    @abc.abstractmethod
    def _ask_registration(self):
        # implemented in sub classes
        return

    @abc.abstractmethod
    def _on_message(self, msg):
        # implemented in sub classes
        pass

    def _send(self, command=DD.bCMD_SEND, msg=None):
        """

        :param command:
        :param msg:
        """
        if not msg:
            msg = []

        self._dealer.send_multipart([DD.bPROTO_VERSION] + [command] + msg)

    def _heartbeat(self):
        self._timeout += 1
        if self._timeout > 3:
            logging.info('Lost connection with broker')
            self._state = DD.S_UNREG
            self._heartbeat_loop.stop()
            self._stream.close()
            self._dealer.close()
            self.on_discon()
            # delete the subscriptions list
            del self._sublist[:]

            self._dealer = self._ctx.socket(zmq.DEALER)
            self._dealer.setsockopt(zmq.LINGER, 1000)
            self._dealer.connect(self._dealerurl)
            self._stream = zmq.eventloop.zmqstream.ZMQStream(self._dealer, self._IOLoop)
            self._stream.on_recv(self._on_message)

            self._register_loop.start()
            logging.debug('Trying to register')

    def _ping(self):
        self._send(DD.bCMD_PING)
