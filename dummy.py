#!/usr/bin/python

# Simulator MQTT Agent
# For testing process control and failover of the overwatch core
#
# Generates a random 
# Joins MQTT bus
# Maintains LWT and client status
#
# Simulation Modes:
# - Exit after a random length of time
#

import os, urlparse
from fnmatch import fnmatch, fnmatchcase
import random
import time

import paho.mqtt.client as paho

# Define event callbacks
def on_connect(mosq, obj, rc):
    pass
    #print("rc: " + str(rc))

def on_it100_message(mosq, obj, msg):
    # msg.topic
    # msg.payload
    pass

def on_message(mosq, obj, msg):
    # msg.topic
    # msg.payload
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

def on_publish(mosq, obj, mid):
    pass
    #print("mid: " + str(mid))

def on_subscribe(mosq, obj, mid, granted_qos):
    pass
    #print("Subscribed: " + str(mid) + " " + str(granted_qos))

def on_log(mosq, obj, level, string):
    print(string)

clientName = "SimNode" + str(random.randrange(1000, 9999, 2))

mqttc = paho.Client(clientName, True)
# Assign event callbacks
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Connect
#mqttc.username_pw_set(url.username, url.password)
mqttc.will_set('clients/' + clientName, 'offline', 0, False)
mqttc.connect("172.23.2.5", 1883)

# Start subscribe, with QoS level 0
mqttc.subscribe(clientName + "/#", 0)
# mqttc.message_callback_add("alarm/it100/#", on_it100_message)

# Continue the network loop, exit when an error occurs
print("Started MQTT Dummy Client with client ID: " + clientName)

# Publish healthy report; Functioning per normal
mqttc.publish("clients/" + clientName, "healthy")

mqttc.loop_start()

randomExitTime = random.randrange(5*60,1*60*60,1)
#print("faking an exit in " + str(randomExitTime) + " seconds")

while randomExitTime:
    randomExitTime = randomExitTime - 1
    time.sleep(1)

# exit non-forcefully
mqttc.loop_stop(False)

# we need to exit with an error code or something
