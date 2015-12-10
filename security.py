#!/usr/bin/python

# Physical Security Agent
# Provides logic to building security
# Monitors alarm systems and sensors
# Creates alerts and acts on alarms

# Provides concept of occupancy for buildings and rooms

# Inputs:
# IT100 DSC Security System
# Alternative GPIO

# Generic Abstract Alarm System
# Alarms have zones and partitions
# Zones have various states and events
# Partitions have states and events
# Partitions can be armed/etc

# Outputs:
# Alerts --> MQTTWARN

import os, urlparse
from fnmatch import fnmatch, fnmatchcase
import time

import paho.mqtt.client as paho

# Define event callbacks
def on_connect(mosq, obj, rc):
    #print("rc: " + str(rc))
    pass

def on_it100_message(mosq, obj, msg):
    if (fnmatch(msg.topic, 'alarm/event') == True):
        print("IT100 Event Message")
        if (msg.payload == "alarm"):
            print("We have ourselves an alarm!")
            #mqttc.publish("comms/sms/2507556998", "HOUSE ALARM!!")
            mqttc.publish("mqttwarn/alarm", "house alarm")
        if (msg.payload == "alarm_restoral"):
            mqttc.publish("comms/alert", "House Alarm Activated")
            #mqttc.publish("comms/sms/2507556998", "ALL CLEAR! House alarm restored.")
            print("We are all clear now!")
    elif (fnmatch(msg.topic, 'alarm/it100/partition/[0-9]*/event') == True):
        print("IT100 Partition Event Message: " + msg.payload)

def zoneStatusChange():
    pass

def on_message(mosq, obj, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

def on_publish(mosq, obj, mid):
    pass
    #print("mid: " + str(mid))

def on_subscribe(mosq, obj, mid, granted_qos):
    pass
    #print("Subscribed: " + str(mid) + " " + str(granted_qos))

def on_log(mosq, obj, level, string):
    print(string)

clientName = "SecurityAgent"
mqttc = paho.Client(clientName)
# Assign event callbacks
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Uncomment to enable debug messages
#mqttc.on_log = on_log

# Parse CLOUDMQTT_URL (or fallback to localhost)
url_str = os.environ.get('CLOUDMQTT_URL', 'mqtt://172.23.2.5:1883')
url = urlparse.urlparse(url_str)

# Connect
#mqttc.username_pw_set(url.username, url.password)
mqttc.will_set('clients/' + clientName, 'offline', 0, False)
mqttc.connect(url.hostname, url.port)

# Start subscribe, with QoS level 0
mqttc.subscribe("alarm/#", 0)
mqttc.message_callback_add("alarm/it100/#", on_it100_message)

# Functioning per orders
mqttc.publish("clients/" + clientName, "healthy")

systems = []
dsc = '{"name":"DSC Power632","module":"it100"}'
systems.append(dsc)

partitions = []
office = '{"type":"virtual",name":"Office","zones":[{"source" : "it100", "zone" : 1}, {"source":"it100","zone":2}]}'
partitions.append(office)

# blocking loop with a KeyboardInterrupt exit
try:
    while True:
        mqttc.loop()
        time.sleep(0.1)
        pass

except KeyboardInterrupt:

    print("Received keyboard interrupt.  Shutting down..")
