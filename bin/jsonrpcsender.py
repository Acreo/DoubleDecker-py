#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import json
import sys

from jsonrpcclient.request import Notification
from jsonrpcserver.exceptions import ServerError
from jsonrpcserver import Methods, dispatch
from doubledecker.clientSafe import ClientSafe

#from cadv_monitor import CAdvisorMonitorThread

__author__ = 'Umar Toseef'
__email__ = 'umar.toseef@eict.de'

# Based on HTTP error codes
REQUEST_ACCEPTED = 201
REQUEST_FAILED = 400
REQUEST_NOT_ACCEPTED = 404
CLIENT_STATUS_CONNECTED = 1
CLIENT_STATUS_DISCONNECTED = 2


class JSONRPCSender(ClientSafe):
    """
    cAdvisor DoubleDecker client
    """

    def __init__(self, name, dealer_url, key_file, target=None, params=None):
       # print("name ", name, " dealer_url ", dealer_url , " keyfile ", key_file , " target ", target , " params " , params  )
        super().__init__(name, dealer_url, key_file)

        self.name = name
        self.target = target
        self.json_params = params
        self.to_monitor = dict()
        self.logger = logging.getLogger("DDClient")


    def on_data(self, src, msg):
        self.logger.debug("Received notification")

    def on_pub(self, src, topic, msg):
        self.logger.debug("Received publication")

    def on_reg(self):
        self.logger.warning("Registered with broker")
        self.STATE = CLIENT_STATUS_CONNECTED
        method = self.json_params['method']
        del self.json_params['method']
        rpc_obj_json = str(Notification(method, **self.json_params))
        print("Sending message %s"%rpc_obj_json)        
        self.sendmsg(self.target, rpc_obj_json)
        self.publish('unify:mmp', rpc_obj_json)
        self.shutdown()

    def on_discon(self):
        self.logger.warning("Disconnected from broker")

    def on_error(self, code, msg):
        self.logger.warning("DD Client ERROR:%s Message:%s" % (str(code), str(msg)))




if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="CAdvisor Aggregator DoubleDecker Client")
    parser.add_argument(
        '-d',
        "--dealer",
        help='URL to connect DEALER socket to, "tcp://1.2.3.4:5555"',
        nargs='?',
        default='tcp://127.0.0.1:5555')
    parser.add_argument(
        '-n',
        "--name",
        help='name of this client',
        nargs='?',
        default="jsonsender")
    parser.add_argument(
        '-t',
        "--target",
        help='who to send to',
        nargs='?',
        default=None)
    parser.add_argument(
        '-p',
        '--publish',
        help='who to send to',
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
        help='keyfile to use)',
        nargs='?',
        default="/etc/doubledecker/public-keys.json")

    args, unknown_args = parser.parse_known_args()

    if not args.target and not args.publish:
        print("You need to supply a target or topic")
        print("E.g., run method 'hello' with paramter 'hello=world'")
        print("Example: ./jsonrpcsender.py -t cadv -n testcli --method hello  --hello world")
        sys.exit(1)
        

    d = {}
    for arg in unknown_args:
        if arg.startswith('--'):  # O
            _, opt = arg.split('--')
            d[opt] = None
        else:  # V
            if opt:
                d[opt] = arg  # NOTE: produces NameError if an orphan encountered
                opt = None

    with_vals = {k: v for k, v in d.items() if v}
    without_vals = [k for k, v in d.items() if not v]

    numeric_log_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_log_level, int):
        raise ValueError('Invalid log level: %s' % args.loglevel)
    logging.basicConfig( level=numeric_log_level,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    print(args)
    logging.info("Starting DDClient name: %s dealer: %s " % (args.name, args.dealer))
    client = JSONRPCSender(args.name, args.dealer, args.keyfile, target=args.target, params=with_vals)
    try:
        client.start()
    except KeyboardInterrupt as e:
        print("\n--KeyboardInterrupt--")
        client.reset_monitoring()
        try:
            client.shutdown()
        except ValueError:
            pass
