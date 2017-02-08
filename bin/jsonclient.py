#!/usr/bin/python3
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import
from builtins import dict
from future import standard_library

standard_library.install_aliases()
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

import argparse
import logging
from doubledecker.clientSafe import ClientSafe
import json
import sys

# from collections import deque

# Example client taking JSON commands as input on STDIN
# And printing incoming messages as JSON to STDOUT


class SecureCli(ClientSafe):
    def on_data(self, src, data):
        msg = dict()
        msg["type"] = "data"
        msg["src"] = src.decode()
        msg["data"] = data.decode()
        try:
            msg["data"] = json.loads(msg["data"])
        except ValueError:
            pass
        print(json.dumps(msg))

    def on_reg(self):
        msg = dict()
        msg["type"] = "reg"
        print(json.dumps(msg))
        for topic in self.mytopics:
            self.subscribe(*topic)
        self._IOLoop.remove_handler(sys.stdin.fileno())
        self._IOLoop.add_handler(sys.stdin.fileno(),self.on_stdin,self._IOLoop.READ)

    def on_discon(self):
        msg = dict()
        msg["type"] = "discon"
        print(json.dumps(msg))

    def on_error(self, code, error):
        msg = dict()
        msg["type"] = "error"
        msg["code"] = code
        msg["error"] = str(error)
        print(json.dumps(msg))

    def on_pub(self, src, topic, data):
        msg = dict()
        msg["type"] = "pub"
        msg["src"] = src.decode()
        msg["topic"] = topic.decode()
        msg["data"] = data.decode()
        try:
            msg["data"] = json.loads(msg["data"])
        except ValueError:
            pass
        print(json.dumps(msg))

    def on_stdin(self, fp, *kargs):        
        data = sys.stdin.readline()
        try:
            res = json.loads(data)
        except ValueError as e:
            print("Caught error while reading stdin, ", e)
            res = dict()

        if "type" in res:
            if res['type'] == "notify":
                if type(res['data']) is str:
                    self.sendmsg(res['dst'], res['data'])
                else:
                    print("json.dumps")
                    self.sendmsg(res['dst'], json.dumps(res['data']))
            elif res['type'] == "pub":
                if type(res['data']) is str:
                    self.publish(res['topic'], res['data'])
                else:
                    print("json.dumps")
                    self.publish(res['topic'], json.dumps(res['data']))
                
            elif res['type'] == "sub":
                if 'topc' in res:
                    self.subscribe(res['topc'], res['scope'])
                elif 'topic' in res:
                    self.subscribe(res['topic'], res['scope'])
            else:
                print(
                    json.dumps(
                        {"type": "error",
                         "data": "Command '{0!s}' not implemented".format(
                             res['type'])}))
        else:
            print(json.dumps({"type": "error", "data": "Couldn't parse JSON"}))

    def run(self, topics):
        self.mytopics = list()
        if topics:
            try:
                for top in topics.split(","):
                    if not len:
                        return
                    (topic, scope) = top.split("/")
                    self.mytopics.append((topic, scope))
            except ValueError:
                logging.error("Could not parse topics!")
                sys.exit(1)
        self.start()

    def exit_program(self, *args):
        self.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generic message client")
    parser.add_argument('name', help="Identity of this client")
    parser.add_argument(
        '-d',
        "--dealer",
        help='URL to connect DEALER socket to, "tcp://1.2.3.4:5555"',
        nargs='?',
        default='tcp://127.0.0.1:5555')
    parser.add_argument(
        '-u',
        "--unsafe",
        action='store_true',
        help='Secure client',
        default=False)
    parser.add_argument(
        '-f',
        "--logfile",
        help='File to write logs to',
        nargs='?',
        default=None)
    parser.add_argument(
        '-l',
        "--loglevel",
        help='Set loglevel (DEBUG, INFO, WARNING, ERROR, CRITICAL)',
        nargs='?',
        default="INFO")

    parser.add_argument(
        '-k',
        "--keyfile",
        help='File containing the encryption/authentication keys)',
        nargs='?',
        required=True)

    parser.add_argument(
        '-t', "--topics",
        help='Comma separated list of topics/scopes, e.g. "topic1/all,topic2/node"',
        nargs='?', default=None)

    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {0!s}'.format(args.loglevel))
    if args.logfile:
        logging.basicConfig(format='%(levelname)s:%(message)s', filename=args.logfile, level=numeric_level)
    else:
        logging.basicConfig(format='%(levelname)s:%(message)s', filename=args.logfile, level=numeric_level)

    genclient = SecureCli(name=args.name, dealerurl=args.dealer, keyfile=args.keyfile, threaded=False)
    logging.debug("Starting DoubleDecker example client")
    logging.debug("See ddclient.py for how to send/recive and publish/subscribe")
    genclient.run(args.topics)
