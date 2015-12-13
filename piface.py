#!/usr/bin/python

# piface mqtt io adapter
# maps mqtt messages to piface commands and events

# mqtt io brings
# - config loaded from json
#   - either commandline argument supplied, or
#   - automatically attempt scriptname.json
# - persistent state with disk cache (json)
#

import sys, os, urlparse
from fnmatch import fnmatch, fnmatchcase
import time
import socket
import re

import paho.mqtt.client as paho
import json, pprint

import pifacedigitalio as pfio

# PIFACE CONSTANTS
NUM_DIO_INPUTS = 8
NUM_DIO_OUTPUTS = 8

# calculate real application path for state cache
scriptNameBase = "piface"
appPath = os.path.dirname(os.path.realpath(sys.argv[0]))
stateCacheFile = "{0}/{1}.cache".format(appPath, scriptNameBase)

# Check for commandline arguments
if (len(sys.argv) < 2):
	# attempt to load from script_name.cache
	try:
		with open("{0}/{1}.json".format(appPath, scriptNameBase)) as data_file:
			config = json.load(data_file)
	except:
		print("needs config; eg. piface.py config.json")
		exit()
else:
	# Check if config file supplied is accessible,
	# otherwise quit
	if not os.path.isfile(sys.argv[1]):
		print("cannot access " + sys.argv[1])
		exit()

	# Load JSON configuration from disk
	try:
		with open(sys.argv[1]) as data_file:
			config = json.load(data_file)
	except:
		print("unable to process " + sys.argv[1])
		exit()


# Define event callbacks
def on_connect(mosq, obj, rc):
	mqttc.subscribe("io/{0}/#".format(clientName), 1)
	mqttc.publish('clients/' + clientName + '/status', 'online', 1, True)

def on_message(mosq, obj, msg):
	
	# dio output set
	match = re.search("io/{0}/dio/output/([0-9A-Za-z]*)/set".format(clientName), msg.topic)
	if match:
		setDigitalOutput(match.group(1), msg.payload)

	# dio output set
	match = re.search("io/{0}/dio/input/([0-9A-Za-z]*)/pullup/set".format(clientName), msg.topic)
	if match:
		setDigitalInputPullup(match.group(1), msg.payload)

def on_publish(mosq, obj, mid):
    pass

def on_subscribe(mosq, obj, mid, granted_qos):
    pass

def on_log(mosq, obj, level, string):
	pass

def writeLog(message, level = "debug"):
	mqttc.publish("log/" + clientName + "/" + level, message)

def setDigitalOutput(channel, value):

	# check that requested channel exists
	channel = int(channel)
	if (channel < 0) or (channel >= NUM_DIO_OUTPUTS):
		# todo throw exception
		writeLog("channel of {0} does not match 0-{1}".format(channel,NUM_DIO_OUTPUTS-1), "error")
		return True
	
	# substitute supplied value
	if (value == "on"): value = 1
	if (value == "off"): value = 0
	if (value == "high"): value = 1
	if (value == "low"): value = 0

	value = int(value)

	if not ((value == 1) or (value == 0)):
		# todo throw exception
		writeLog("value of {0} does not match 0 or 1".format(value), "error")
		return True

	# track, publish, and set state
	# cache state to disk
	state["outputs"][channel]["state"] = value
	mqttc.publish("io/{0}/dio/output/{1}/state".format(clientName, channel), value, 1, True)
	pfio.digital_write(channel, value)
	writeState()
	
def setDigitalInputPullup(channel, value):

	# check that requested channel exists
	channel = int(channel)
	if (channel < 0) or (channel >= NUM_DIO_INPUTS):
		# todo throw exception
		return True
	
	# substitute supplied value
	if (value == "on"): value = 1
	if (value == "off"): value = 0
	if (value == "high"): value = 1
	if (value == "low"): value = 0

	value = int(value)
	
	if not (value == 1) or (value == 0):
		writeLog("value of {0} does not match 0 or 1".format(value), "error")
		return True

	# track, publish, and set state
	# cache state to disk
	state["inputs"][channel]["pullup"] = value
	mqttc.publish("io/{0}/dio/in/{1}/pullup".format(clientName, channel), value, 1, True)
	pfio.digital_write_pullup(channel, value)
	writeState()

def loadState():
	
	global state
	
	if not os.path.isfile(stateCacheFile):
		return True
		
	try:
		with open("{0}/piface.cache".format(appPath)) as data_file:
			state = json.load(data_file)
			writeLog("loaded piface cached state from disk")
	except:
		writeLog("unable to process piface cached state ({0}/piface.cache)".format(appPath))
		return True

	# resume IO state and settinsg
	for i in range(len(state["outputs"])):
		pfio.digital_write(i, state["outputs"][i]["state"])
	for i in range(len(state["inputs"])):
		pfio.digital_write_pullup(i, state["inputs"][i]["pullup"])
		state["inputs"][i]["state"] = pfio.digital_read(i)

	return False

def writeState():
	
	global state
	with open("{0}/piface.cache".format(appPath), 'w') as outfile:
		json.dump(state, outfile, indent=1)
	
def initState():
	
	# Build state array
	global state
	state  = {}
	
	state["inputs"] = []
	for i in range(NUM_DIO_INPUTS):
		input = {}
		state["inputs"].append(input)
		state["inputs"][i]["state"] = 0
		state["inputs"][i]["pullup"] = 0
		
	state["outputs"] = []
	for i in range(NUM_DIO_OUTPUTS):
		output = {}
		state["outputs"].append(output)
		state["outputs"][i]["state"] = 0
###############################

pfio.init()

clientName = config["mqttClientName"]
mqttc = paho.Client(clientName)

# Load state from disk or re-initialize if
# not available or error produced
state = {}
if loadState():
	initState()

# Assign event callbacks for MQTT client
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Set MQTT Last Will and Testament to maintain
# client status tracking
# maintaind during on_connect callback also
mqttc.will_set('clients/' + clientName + '/status', 'offline', 1, True)
mqttc.connect(config["mqttRemoteHost"], config["mqttRemotePort"])

# blocking loop with a KeyboardInterrupt exit 
running = True
try:
    while running:
	
		# todo, no debouncing or anything 
		for i in range(NUM_DIO_INPUTS):
			inputstate = pfio.digital_read(i)
			# if change detected
			if state["inputs"][i]["state"] != inputstate:
				state["inputs"][i]["state"] = inputstate
				mqttc.publish("io/{0}/dio/input/{1}/state".format(clientName, i), inputstate, 2, True)
				writeState()
		
		mqttc.loop(timeout=0.01)

# Keyboard interrupt has been received,
# attempt to cease the mainloop gracefully
except KeyboardInterrupt:
	running = False
	print("Received keyboard interrupt.  Shutting down..")
