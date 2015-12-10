#!/usr/bin/python

# Reporter
# Provide reporting logic to system
# Can setup filters to watch for particular data
# and report this to alternative means

import os, urlparse
from fnmatch import fnmatch, fnmatchcase
import time
import socket

import paho.mqtt.client as paho

#import urllib2, urllib
import json, pprint

import re

BUFFER_SIZE = 1024
TARGET_TOPIC = "environment/winchelsea/wind"

# Define event callbacks
def on_connect(mosq, obj, rc):
    pass

def on_message(mosq, obj, msg):
    pass

def on_publish(mosq, obj, mid):
    pass

def on_subscribe(mosq, obj, mid, granted_qos):
    pass

def on_log(mosq, obj, level, string):
    print(string)

clientName = "RocAnemometer"
mqttc = paho.Client(clientName)
# Assign event callbacks
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Parse CLOUDMQTT_URL (or fallback to localhost)
url_str = os.environ.get('CLOUDMQTT_URL', 'mqtt://172.23.2.5:1883')
url = urlparse.urlparse(url_str)

# Connect
#mqttc.username_pw_set(url.username, url.password)
mqttc.will_set('clients/' + clientName + '/status', 'offline', 0, False)
mqttc.connect(url.hostname, url.port)

# Start subscribe, with QoS level 0
mqttc.subscribe("alarm/#", 2)
#mqttc.message_callback_add("alarm/event/#", on_it100_message)

serviceStatus = {}
serviceStatus["status"] = "healthy"
serviceStatus["sub"] = {}
serviceStatus["sub"]["serialip"] = {}
serviceStatus["sub"]["serialip"]["description"] = "Serial Device Server"
serviceStatus["sub"]["serialip"]["status"] = "healthy"
serviceStatus["sub"]["anemometer"] = {}
serviceStatus["sub"]["anemometer"]["description"] = "Ultrasonic Anemomometer"
serviceStatus["sub"]["anemometer"]["depends"] = "serialip"

# should be able to get overall status easily
# clients/anemometer/status ["health"] = healthy
def sitRep():
    mqttc.publish("clients/" + clientName + "/status", serviceStatus["status"])
    mqttc.publish("clients/" + clientName + "/fullstatus", json.dumps(serviceStatus))

sitRep()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("powderpoint.dyndns.org", 5501))

# blocking loop with a KeyboardInterrupt exit
try:
    while True:
        data = s.recv(BUFFER_SIZE)
        elements = data.split(",")
        mqttc.publish(TARGET_TOPIC, '{"speed":"' + elements[0]+ '","direction":"' + elements[1] + '"}')
        mqttc.loop()
        time.sleep(0.1)
        pass

except KeyboardInterrupt:
    print("Received keyboard interrupt.  Shutting down..")


# clean up socket
s.close()