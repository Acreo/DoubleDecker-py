#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import super
from builtins import str
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
import urwid
from collections import deque
import time
import json
import datetime

# Inherit ClientSafe and implement the abstract classes
# ClientSafe does encryption and authentication using ECC (libsodium/nacl)


class SecureCli(ClientSafe):


    def add_msg(self, msg):
        st = datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S')
        self.msg_list.append("{0!s}:{1!s}".format(st, msg))
        self.messages = ""

        for n in self.msg_list:
            self.messages = self.messages + n + "\n"
        self.body[-1].set_text(self.messages)

    def on_data(self, src, msg):
        self.add_msg("DATA from {0!s}: {1!s}".format(str(src), str(msg)))

    def on_reg(self):
        self.registered = True
        self.update_main_text()

    def on_discon(self):
        self.registered = False
        self.update_main_text()

    def on_error(self, code, msg):
        if code == ClientSafe.E_REGFAIL:
            self.add_msg(
                "ERROR - Registration failed, reason: {0!s}".format(msg[0]))
        elif code == ClientSafe.E_VERSION:
            self.add_msg("ERROR - Registration failed, wrong protcol version!")
        elif code == ClientSafe.E_NODST:
            self.add_msg("ERROR - No destination: {0!s}".format(msg))
        else:
            self.add_msg("ERROR - unknwon ({0:d},{1!s})".format(code, msg))

    def on_pub(self, src, topic, msg):
        msgstr = "PUB {0!s} from {1!s}: {2!s}".format(
            str(topic), str(src), str(msg))
        self.add_msg(msgstr)

    def update_main_text(self):
        if self.registered:
            state = "Connected"
        else:
            state = "Disconnected"

        substr = json.dumps(self.subscriptions)
        self.main_text = (
            "DoubleDecker {0!s} Dealer: {1!s} State: {2!s}\nSubscriptions: {3!s}".format(
                self._name.decode(),
                self._dealerurl.decode(),
                state,
                substr))
        try:
            self.body[0].set_text(self.main_text)
        except AttributeError:
            pass

    def run(self):
        self.msg_list = deque(maxlen=10)
        self.messages = ""
        self.main_text = ""

        self.pub_msg = ""
        self.pub_topic = ""

        self.notify_dest = ""
        self.notify_msg = ""

        self.sub_scope = ""
        self.sub_topic = ""

        self.unsub_scope = ""
        self.unsub_topic = ""

        self.subscriptions = []
        self.registered = False
        self.choices = ["Subscribe", "Unsubscribe", "Exit"]
        self.update_main_text()
        self.main = urwid.Padding(self.menu(), left=2, right=2)
        try:
            urwid.MainLoop(
                self.main,
                palette=[('reversed', 'standout', '')],
                event_loop=urwid.TornadoEventLoop(genclient._IOLoop)).run()
        except KeyboardInterrupt:
            self.shutdown()

    def menu(self):
        self.body = [urwid.Text(self.main_text), urwid.Divider(div_char='~')]

        notify_button = urwid.Button("Send Notifcation")
        urwid.connect_signal(
            notify_button,
            'click',
            self.notify_handler,
            "notify")
        self.body.append(
            urwid.AttrMap(
                notify_button,
                None,
                focus_map='reversed'))

        publish_button = urwid.Button("Publish message")
        urwid.connect_signal(
            publish_button,
            'click',
            self.publish_handler,
            "publish")
        self.body.append(
            urwid.AttrMap(
                publish_button,
                None,
                focus_map='reversed'))

        subscribe_button = urwid.Button("Subscribe to topic")
        urwid.connect_signal(
            subscribe_button,
            'click',
            self.subscribe_handler,
            "subscribe")
        self.body.append(
            urwid.AttrMap(
                subscribe_button,
                None,
                focus_map='reversed'))

        unsubscribe_button = urwid.Button("Unsubscribe from topic")
        urwid.connect_signal(
            unsubscribe_button,
            'click',
            self.unsubscribe_handler,
            "unsubscribe")
        self.body.append(
            urwid.AttrMap(
                unsubscribe_button,
                None,
                focus_map='reversed'))

        exit_button = urwid.Button("Quit DoubleDecker demo client")
        urwid.connect_signal(exit_button, 'click', self.exit_program, "")
        self.body.append(urwid.AttrMap(exit_button, None, focus_map='reversed'))
        self.body.append(urwid.Divider(div_char='~'))
        self.body.append(urwid.Text("Messages:"))
        self.body.append(urwid.Text(self.messages))

        return urwid.ListBox(urwid.SimpleFocusListWalker(self.body))

    def on_not_dest_change(self, edit, new_edit_text):
        self.notify_dest = new_edit_text

    def on_not_msg_change(self, edit, new_edit_text):
        self.notify_msg = new_edit_text

    def notify_handler(self, button, choice):
        destination = urwid.Edit(('I say', u"Destination: "))
        self.reply_notify_dest = urwid.Text(u"")
        message = urwid.Edit(('I say', u"Message: "))
        self.reply_notify_msg = urwid.Text(u"")
        ret = urwid.Button(u'Notify')
        urwid.connect_signal(destination, 'change', self.on_not_dest_change)
        urwid.connect_signal(message, 'change', self.on_not_msg_change)
        urwid.connect_signal(ret, 'click', self.return_main, "notify")
        pile = urwid.Pile([destination, message,  ret])
        top = urwid.Filler(pile, valign='top')
        self.main.original_widget = top

    def on_pub_topic_change(self, edit, new_edit_text):
        self.pub_topic = new_edit_text

    def on_pub_msg_change(self, edit, new_edit_text):
        self.pub_msg = new_edit_text

    def publish_handler(self, button, choice):
        topic = urwid.Edit(('I say', u"Topic: "))
        message = urwid.Edit(('I say', u"Message: "))
        ret = urwid.Button(u'Publish')
        urwid.connect_signal(topic, 'change', self.on_pub_topic_change)
        urwid.connect_signal(message, 'change', self.on_pub_msg_change)
        urwid.connect_signal(ret, 'click', self.return_main, "publish")
        pile = urwid.Pile([topic, message,  ret])
        top = urwid.Filler(pile, valign='top')
        self.main.original_widget = top

    def on_sub_topic_change(self, edit, new_edit_text):
        self.sub_topic = new_edit_text

    def on_sub_scope_change(self, edit, new_edit_text):
        self.sub_scope = new_edit_text

    def subscribe_handler(self, button, choice):
        self.sub_topic = ''
        self.sub_scope = ''
        topic = urwid.Edit(('I say', u"Topic: "))
        scope = urwid.Edit(
            ('I say', u"Scope(all/region/cluster/node/noscope: "))
        ret = urwid.Button(u'Subscribe')
        urwid.connect_signal(topic, 'change', self.on_sub_topic_change)
        urwid.connect_signal(scope, 'change', self.on_sub_scope_change)
        urwid.connect_signal(ret, 'click', self.return_main, "subscribe")
        pile = urwid.Pile([topic, scope,  ret])
        top = urwid.Filler(pile, valign='top')
        self.main.original_widget = top

    def on_unsub_topic_change(self, edit, new_edit_text):
        self.unsub_topic = new_edit_text

    def on_unsub_scope_change(self, edit, new_edit_text):
        self.unsub_scope = new_edit_text

    def unsubscribe_handler(self, button, choice):
        topic = urwid.Edit(('I say', u"Topic: "))
        scope = urwid.Edit(
            ('I say', u"Scope(all/region/cluster/node/noscope: "))
        ret = urwid.Button(u'Unsubscribe')
        urwid.connect_signal(topic, 'change', self.on_unsub_topic_change)
        urwid.connect_signal(scope, 'change', self.on_unsub_scope_change)
        urwid.connect_signal(ret, 'click', self.return_main, "unsubscribe")
        pile = urwid.Pile([topic, scope,  ret])
        top = urwid.Filler(pile, valign='top')
        self.main.original_widget = top

    def return_main(self, button, cmd='None'):
        if cmd == 'notify':
            self.sendmsg(self.notify_dest, self.notify_msg)

        if cmd == 'publish':
            self.publish(self.pub_topic, self.pub_msg)

        if cmd == 'subscribe':
            substr = "{0!s}/{1!s}".format(self.sub_topic, self.sub_scope)
            self.subscriptions.append(substr)
            try:
                self.subscribe(self.sub_topic, self.sub_scope)
            except BaseException as e:
                self.add_msg("Exception caught : {0!s})".format(str(e)))

        if cmd == 'unsubscribe':
            substr = "{0!s}/{1!s}".format(self.sub_topic, self.sub_scope)
            self.subscriptions.remove(substr)
            self.unsubscribe(self.unsub_topic, self.unsub_scope)

        self.update_main_text()
        self.main.original_widget = self.menu()

    def exit_program(self, *args):
        self.shutdown()
        raise urwid.ExitMainLoop()


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
        default='')

    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: {0!s}'.format(args.loglevel))
    if args.logfile:
        logging.basicConfig(
            format='%(levelname)s:%(message)s',
            filename=args.logfile,
            level=numeric_level)
    else:
        logging.basicConfig(
            format='%(levelname)s:%(message)s',
            filename=args.logfile,
            level=numeric_level)

    genclient = SecureCli(
        name=args.name,
        dealerurl=args.dealer,
        keyfile=args.keyfile)

    logging.info("Starting DoubleDecker example client")
    logging.info("See ddclient.py for how to send/recive and publish/subscribe")
    genclient.run()
