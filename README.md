[![Build Status](https://travis-ci.org/Acreo/DoubleDecker-py.svg?branch=master)](https://travis-ci.org/Acreo/DoubleDecker-py)
[![Code Issues](https://www.quantifiedcode.com/api/v1/project/ffd6252b2b444192a5d7ac1779b7f78a/badge.svg)](https://www.quantifiedcode.com/app/project/ffd6252b2b444192a5d7ac1779b7f78a)
[![Code Climate](https://codeclimate.com/github/Acreo/DoubleDecker-py/badges/gpa.svg)](https://codeclimate.com/github/Acreo/DoubleDecker-py)

### WARNING

The python version of the broker is not supported at the moment. Please use the
C version unless you have very specific needs.

### INSTALLATION
DoubleDecker requires Python > 3.3. To install on Ubuntu 15.10, run the install.sh script which performs these actions: 
```bash
#install dependencies 
apt-get update
apt-get install python3-setuptools python3-nacl python3-zmq python3-urwid python3-tornado git
# clone the code
git clone https://github.com/Acreo/DoubleDecker.git
# install the doubledecker module and scripts
cd DoubleDecker-py
sudo python3 setup.py install
# generate public/private keys
cd /etc
mkdir doubledecker
cd doubledecker
# create keys for 4 tenants, public, tenant a, b, and c
ddkeys.py (input "a,b,c")
```

### USAGE
```bash
#First you need to start a broker, you can use the C version available
# at https://github.com/Acreo/DoubleDecker
# start a client from tentant A, called cli1, connect to broker0
ddclient.py -d tcp://127.0.0.1:5555 -k /etc/doubledecker/a-keys.json cli1 a
# start a second client tentant A, called cli2, connect to broker0
ddclient.py -d tcp://127.0.0.1:5555 -k /etc/doubledecker/a-keys.json cli2 a
# now you can use the CLI interface to send notifications
# from cli1 to cli2 or to subscribe and publish messages
# to send a notification from cli1 to cli2
Send Notification -> Destination: cli2 -> Message: hello -> Notify
should result in message "hello" appearing at cli2
# to subscribe to topic "alarms"
Subscribe to topic -> Topic: alarms -> Scope: region -> Subscribe
# to publish on topic alarms
Publish message -> Topic: alarms -> Message: warning -> Publish
```

