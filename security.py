#!/usr/bin/python

# Building Security Agent
# Provides logic to building security
# Monitors alarm systems and sensors
# Creates alerts and acts on alarms

# Provides concept of occupancy for buildings and rooms

# Inputs:
# IT100 DSC Security System
# Alternative GPIO

# Outputs:
# Alerts --> MQTTWARN

import os, urlparse
from fnmatch import fnmatch, fnmatchcase

import paho.mqtt.client as paho

# Define event callbacks
def on_connect(mosq, obj, rc):
    pass
    #print("rc: " + str(rc))

def on_it100_message(mosq, obj, msg):
    if (fnmatch(msg.topic, 'alarm/it100/event') == True):
        print("IT100 Event Message")
        if (msg.payload == "alarm"):
            print("We have ourselves an alarm!")
            mqttc.publish("mqttwarn/alarm", "house alarm")
        if (msg.payload == "alarm_restoral"):
            print("We are all clear now!")
    elif (fnmatch(msg.topic, 'alarm/it100/partition/[0-9]*/event') == True):
        print("IT100 Partition Event Message")

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

mqttc = paho.Client()
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
mqttc.connect(url.hostname, url.port)

# Start subscribe, with QoS level 0
mqttc.subscribe("alarm/#", 0)
mqttc.message_callback_add("alarm/it100/#", on_it100_message)

# Publish a message
# mqttc.publish("hello/world", "my message")

# Continue the network loop, exit when an error occurs
rc = 0
while rc == 0:
    rc = mqttc.loop()
#print("rc: " + str(rc))