# coding=utf-8
import logging
import json
import re

import zmq
import zmq.eventloop.ioloop
import zmq.eventloop.zmqstream
import nacl.utils
import nacl.public
import nacl.encoding

from . import proto as DD
from . import clientInterface as interface


class ClientSafe(interface.Client):
    """ DoubleDecker client with encryption and authentication """

    def __init__(self, name, dealerurl, customer, keyfile):
        """ initialise the class

        Args:
            name: name used to identify the client within the architecture
            dealerurl: address to reach the broker (e.g. tcp://localhost:5555)
            customer: name of the tenant of the client
            keyfile: link to the file containing the keys pair
        Raises:
            RuntimeError if the keyfile can't be found
        """
        super().__init__(name, dealerurl, customer)

        if not keyfile:
            filename = self._customer.decode() + '-keys.json'
        else:
            filename = keyfile
        try:
            with open(filename) as f:
                key = json.load(f)
        except IOError as e:
            print(e)
            raise

        if self._customer.decode() == 'public':
            self._privkey = nacl.public.PrivateKey(
                key['public']['privkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._pubkey = nacl.public.PublicKey(
                key['public']['pubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._cust_box = nacl.public.Box(
                self._privkey,
                self._pubkey)
            ddpubkey = nacl.public.PublicKey(
                key['public']['ddpubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._dd_box = nacl.public.Box(self._privkey, ddpubkey)
            publicpubkey = nacl.public.PublicKey(
                key['public']['publicpubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._hash = key['public']['hash'].encode()
            del key['public']
            # create a nacl.public.Box for each customers in a dict, e.g.
            # self.cust_boxes[a] for customer a
            self._cust_boxes = dict()
            for hash_ in key:
                cust_public_key = nacl.public.PublicKey(
                    key[hash_]['pubkey'],
                    encoder=nacl.encoding.Base64Encoder)
                self._cust_boxes[key[hash_]['r']] = nacl.public.Box(
                    self._privkey, cust_public_key)
        else:
            self._privkey = nacl.public.PrivateKey(
                key['privkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._pubkey = nacl.public.PublicKey(
                key['pubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._cust_box = nacl.public.Box(self._privkey, self._pubkey)
            ddpubkey = nacl.public.PublicKey(
                key['ddpubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._dd_box = nacl.public.Box(
                self._privkey,
                ddpubkey)
            publicpubkey = nacl.public.PublicKey(
                key['publicpubkey'],
                encoder=nacl.encoding.Base64Encoder)
            self._pub_box = nacl.public.Box(self._privkey, publicpubkey)
            self._hash = key['hash'].encode()

        self._nonce = bytearray(nacl.utils.random(nacl.public.Box.NONCE_SIZE))
        self._subscriptions = list()

    def subscribe(self, topic, scope):
        """
        Subscribe to a topic with a given scope
        Args:
            topic: Name of the topic
            scope: all, region, cluster, node or noscope
        Raise:
            SyntaxError if the scope doesn't follow the defined syntax
        """
        if self._state != DD.S_REGISTERED:
            raise ConnectionError

        scopestr = self.check_scope(scope)

        if (topic, scopestr) in self._subscriptions:
            logging.warning("Already subscribed to %s %s", topic, scopestr)
            return
        else:
            self._subscriptions.append((topic, scopestr))
        if scopestr == "noscope":
            logging.debug("Subscribing to %s", topic)
        else:
            logging.debug("Subscribing to %s %s", topic, scopestr)

        self._send(
            DD.bCMD_SUB, [
                self._cookie, topic.encode(), scopestr.encode()])

    def unsubscribe(self, topic, scope):
        """ Unsubscribe from a partiuclar topic and scope

        Args:
            topic: Topic to unsubscribe from
            scope: all, region, cluster, node or noscope
        Raises:
            SyntaxError if the scope doesn't follow the defined syntax
            Connection error if the fucntion is called while unregistered
        """
        if self._state != DD.S_REGISTERED:
            raise ConnectionError

        scopestr = self.check_scope(scope)

        if scopestr == "noscope":
            logging.debug("Unsubscribing from %s", topic)
        else:
            logging.debug("Unsubscribing from %s", topic, scopestr)
        if (topic, scopestr) in self._subscriptions:
            self._subscriptions.remove((topic, scopestr))
        else:
            logging.warning("Not subscribed to %s %s !", topic, scopestr)
            return

        self._send(
            DD.bCMD_UNSUB, [
                self._cookie, topic.encode(), scopestr.encode()])

    @staticmethod
    def check_scope(scope_):
        scope_ = scope_.strip().lower()
        if scope_ == 'all':
            scopestr = "/"
        elif scope_ == 'region':
            scopestr = "/*/"
        elif scope_ == "cluster":
            scopestr = "/*/*/"
        elif scope_ == "node":
            scopestr = "/*/*/*/"
        elif scope_ == "noscope":
            scopestr = "noscope"
        elif re.fullmatch("/((\d)+/)+", scope_):
            # check that scope only contains numbers and slashes
            scopestr = scope_
        else:
            raise SyntaxError(
                "Scope supports ALL/REGION/CLUSTER/NODE/NOSCOPE,\
                or specific values,e.g. /1/2/3/")
        return scopestr

    def publish(self, topic, message):
        """ Publish a message on a topic

        Args:
            topic: Which topic to publish to
            message: The message to publish
        Raises:
            ConnectionError if called while not registered
        """
        if self._state != DD.S_REGISTERED:
            raise ConnectionError
        if isinstance(topic, str):
            topic = topic.encode('utf8')
        if isinstance(message, str):
            message = message.encode('utf8')

        encryptmsg = self._cust_box.encrypt(message, self._get_nonce())
        self._dealer.send_multipart(
            [DD.bPROTO_VERSION, DD.bCMD_PUB, self._cookie, topic, b'', encryptmsg])

    def publish_public(self, topic, message):
        """ Publish a message to a public topic
        (uses different encryption key)

        Args:
            topic: Which topic to publish to
            message: The message to publish
        Raises:
            ConnectionError if called while not registered
        """
        if self._state != DD.S_REGISTERED:
            raise ConnectionError
        if isinstance(topic, str):
            topic = topic.encode('utf8')
        if isinstance(message, str):
            message = message.encode('utf8')

        encryptmsg = self._pub_box.encrypt(message, self._get_nonce())
        self._dealer.send_multipart(
            [DD.bPROTO_VERSION, DD.bCMD_PUB, self._cookie, topic, b'', encryptmsg])

    def sendmsg(self, dst, msg):
        """ Send a notification

        Args:
            dst: Destination for the notification
            msg: Data to send
        Raises:
            ConnectionError if called while not registered
        """
        if self._state != DD.S_REGISTERED:
            raise ConnectionError

        # TODO the non-public -> non-public is the last case checked, as it
        # might be the most common case if would make sense to re-organize this
        # function
        if self._customer == b'public':
            dst_is_public = True
            try:
                split = dst.split('.')
                customer_dst = split[0]
                if customer_dst in self._cust_boxes:
                    dst_is_public = False
            except Exception as e:
                logging.warning("exception caught : {}".format(e))

            if isinstance(dst, str):
                dst = dst.encode('utf8')
            if isinstance(msg, str):
                msg = msg.encode('utf8')

            if dst_is_public:
                # public --> public
                msg = self._cust_box.encrypt(msg, self._get_nonce())
                # print("Sending encrypted data to %s" % dst.decode('utf8'))
                self._send(DD.bCMD_SEND, [self._cookie, dst, msg])
            else:
                # public --> non-public
                msg = self._cust_boxes[customer_dst].encrypt(
                    msg, self._get_nonce())
                # print("Sending encrypted data to %s" % dst.decode('utf8'))
                self._send(DD.bCMD_SEND, [self._cookie, dst, msg])
        else:
            # send to a public or not ?
            dst_is_public = False
            try:
                split = dst.split('.')
                dst_is_public = split[0] == 'public'
            except Exception as e:
                logging.warning("exception caught : {}".format(e))

            if isinstance(dst, str):
                dst = dst.encode('utf8')
            if isinstance(msg, str):
                msg = msg.encode('utf8')

            if dst_is_public:
                # non-public --> public
                msg = self._pub_box.encrypt(msg, self._get_nonce())
                # print("Sending encrypted data to %s" % dst.decode('utf8'))
                self._send(DD.bCMD_SEND, [self._cookie, dst, msg])
            else:
                # non-public --> non-public
                msg = self._cust_box.encrypt(msg, self._get_nonce())
                # print("Sending encrypted data to %s" % dst.decode('utf8'))
                # print("self.R: ", type(self.R), " dst: ", type(dst), " msg:", type(msg) )
                self._send(DD.bCMD_SEND, [self._cookie, dst, msg])

    def _ping(self):
        """ sends the ping to keep the connection with the broker alive """
        self._send(DD.bCMD_PING, [self._cookie])

    def _ask_registration(self):
        """ initiate the registration with the broker """
        self._dealer.setsockopt(zmq.LINGER, 0)
        self._stream.close()
        self._dealer.close()
        self._dealer = self._ctx.socket(zmq.DEALER)
        self._dealer.setsockopt(zmq.LINGER, 1000)
        self._dealer.connect(self._dealerurl)
        self._stream = zmq.eventloop.zmqstream.ZMQStream(
            self._dealer, self._IOLoop)
        self._stream.on_recv(self._on_message)
        self._send(DD.bCMD_ADDLCL, [self._hash])

    def _on_message(self, msg):
        """ callback triggered when a message is received """
        self._timeout = 0
        if msg.pop(0) != DD.bPROTO_VERSION:
            logging.warning('Different protocols in use, message discarded')
            return
        cmd = msg.pop(0)
        if cmd == DD.bCMD_REGOK:
            self._on_message_regok(msg)
        elif cmd == DD.bCMD_DATA:
            self._on_message_data(msg)
        elif cmd == DD.bCMD_DATAPT:
            self.on_data(msg.pop(0), msg)
        elif cmd == DD.bCMD_PONG:
            self._on_message_pong()
        elif cmd == DD.bCMD_CHALL:
            self._on_message_chall(msg)
        elif cmd == DD.bCMD_PUB:
            self._on_message_pub(msg)
        elif cmd == DD.bCMD_PUBPUBLIC:
            self._on_message_pupublic(msg)
        elif cmd == DD.bCMD_SUBOK:
            self._on_message_subok(msg)
        elif cmd == DD.bCMD_ERROR:
            self._on_message_error(msg)
        else:
            logging.warning("Unknown message, got: %i %s", cmd, msg)

    def _on_message_regok(self, msg):
        logging.debug('Registered correctly')
        self._state = DD.S_REGISTERED
        self._register_loop.stop()
        self._cookie = msg.pop(0)
        if isinstance(self._cookie, str):
            self._cookie = self._cookie.encode('utf8')
        self._heartbeat_loop.start()
        self._send(DD.bCMD_PING, [self._cookie])
        for (topic, scopestr) in self._subscriptions:
            self._send(
                DD.bCMD_SUB, [self._cookie, topic.encode(), scopestr.encode()])
        self.on_reg()

    def _on_message_data(self, msg):
        source = msg.pop(0)
        if self._customer == b'public':
            customer_source = source.decode().split('.')[0]
            if customer_source in self._cust_boxes:
                # non-public --> public
                msg = self._cust_boxes[customer_source].decrypt(msg.pop())
            else:
                # public --> public
                msg = self._cust_box.decrypt(msg.pop())
        else:
            customer_source = source.decode().split('.')[0]
            if customer_source == 'public':
                # public --> non-public
                msg = self._pub_box.decrypt(msg.pop())
            else:
                # non-public --> non-public
                msg = self._cust_box.decrypt(msg.pop())
        self.on_data(source, msg)

    def _on_message_pong(self):
        ioloop = zmq.eventloop.ioloop.IOLoop.current()
        ioloop.add_timeout(ioloop.time() + 1.5, self._ping)

    def _on_message_chall(self, msg):
        logging.debug("Got challenge...")
        self._state = DD.S_CHALLENGED
        encryptednumber = msg.pop(0)
        decryptednumber = self._dd_box.decrypt(encryptednumber)
        # Send the decrypted number, his hash and his name for the
        # registration
        self._send(
            DD.bCMD_CHALLOK, [
                decryptednumber, self._hash, self._name])

    def _on_message_pub(self, msg):
        src = msg.pop(0)
        topic = msg.pop(0)
        encryptmsg = msg.pop(0)
        if self._customer == b'public':
            src_customer = src.decode().split('.')[0]
            if src_customer in self._cust_boxes:
                # non-public --> public
                decryptmsg = self._cust_boxes[
                    src_customer].decrypt(encryptmsg)
            else:
                # public --> public
                decryptmsg = self._cust_box.decrypt(encryptmsg)
        else:
            # non-public --> non-public
            decryptmsg = self._cust_box.decrypt(encryptmsg)
        self.on_pub(src, topic, decryptmsg)

    def _on_message_pubpublic(self, msg):
        src = msg.pop(0)
        topic = msg.pop(0)
        self.on_pub(src, topic, msg)

    def _on_message_subok(self, msg):
        topic = msg.pop(0).decode()
        scope = msg.pop(0).decode()
        tt = "{0!s}{1!s}".format(topic, scope)
        if tt not in self._sublist:
            self._sublist.append(tt)
        else:
            logging.error("Already subscribed to topic %s", topic)
            self._dealer.send_multipart(
                [DD.bPROTO_VERSION, DD.bCMD_UNSUB, topic.encode()])

    def _on_message_error(self, msg):
        self.on_error(int.from_bytes(msg.pop(0), byteorder='little'), msg)

    def _get_nonce(self):
        index = nacl.public.Box.NONCE_SIZE - 1
        while True:
            try:
                self._nonce[index] += 1
                return bytes(self._nonce)
            except ValueError:
                self._nonce[index] = 0
                index -= 1

    @staticmethod
    def _cli_usage():
        print("Commands: ")
        print("help                     - show this help")
        print(
            "send        [client] [message] - send an encrypted message to client")
        print(
            "sendPT      [client] [message] - send a plain text message to client")
        print(
            "sendpublic  [public client] [message] - send message to a public client")
        print("pub         [topic]  [message] - publish message on topic")
        print(
            "pubpublic   [topic]  [message] - publish message on public topic")
        print("sub         [topic]            - subscribe to messages in topic")
        print("unsub       [topic]            - subscribe to messages in topic")
        print('exit                           - unregister and exit')
