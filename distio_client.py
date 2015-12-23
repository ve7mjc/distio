# distio_client
#
# MQTT mapped IO Adapter Superclass
#
# MQTTC Topics
#
# Last Will and Testament: clients/{client_name}/status offline
# Connect Hello: clients/{client_name}/status online
# 
# Basic Structure
# io/{client-name}/{io-class}/{channel_num}
#
# Digital Inputs
# Commands:
# io/{client-name}/dio-input/{channel_num}/set/{parameter}
# Parameters:
#  - pullup: set input pullups if available (0,1)
#  - 
# Responses:
# io/{client-name}/dio-input/{channel_num}/state [basic value (0,1)]
# io/{client-name}/dio-input/{channel_num}/event/transition/{direction} [json event]
#
# Digital Outputs
# Commands:
# io/{client-name}/dio-output/{channel_num}/set/{parameter} [value]
# Parameters: 
#   value - set output state (0,1) or ("on", "off")
#   pullup - 
# Responses:
# io/{client-name}/dio-output/{channel_num}/state [value]
#

import sys, os
from fnmatch import fnmatch, fnmatchcase
import time
import socket
import re

import paho.mqtt.client as paho
import json, pprint

from distio_pulse import distio_pulse

QOS_AT_MOST_ONCE = 0
QOS_AT_LEAST_ONCE = 1
QOS_EXACTLY_ONCE = 2

class distio_client():

	def __init__(self, config=None):

		# default hardware template
		self.num_dio_inputs = 0
		self.num_dio_outputs = 0
		self.num_adc_inputs = 0
		self.num_dac_outputs = 0
		self.digitalInputPollingEnabled = True
		
		# debugging and performance
		self.debugEnabled = False
		self.inputPollTimeMs = 0

		self.auto_run = True

		# Load application specific configuration
		# Supply commandline argument as default
		self.loadConfig(sys.argv[0])
		
		# call subclass init, so we have the config options
		self.init()

		# Configure MQTTC Client
		self.clientName = self.config["mqttClientName"]
		self.mqttc = paho.Client(self.clientName)
		self.mqttc.on_message = self._onMqttMessage
		self.mqttc.on_connect = self._onMqttConnect
		self.mqttc.on_publish = self._onMqttPublish
		self.mqttc.on_subscribe = self._onMqttSubscribe

		# Set MQTT Last Will and Testament to maintain
		# client status tracking
		# maintained during on_connect callback also
		if self.debugEnabled:
			print("Connecting to MQTT Broker at {0}:{1}".format(self.config["mqttRemoteHost"], self.config["mqttRemotePort"]))
		self.mqttc.will_set("clients/{0}/status".format(self.clientName), 'offline', QOS_AT_LEAST_ONCE, True)
		self.mqttc.connect(self.config["mqttRemoteHost"], self.config["mqttRemotePort"])
		
		# call mqttc loop to start and operate in 
		# a dedicated thread
		self.mqttc.loop_start()

		# Initialize state and then attemp to recover
		# from a disk based cache
		self.loadState()

		# we are not yet resuming continuous pulsing
		# outputs from persistent state cache from disk
		self.inputStateCheck = []
		self.dioOutputPulse = []
		for i in range(self.num_dio_outputs):
			self.dioOutputPulse.append(distio_pulse())

		# automatically begin mainloop unless
		# directed otherwise in reimplemented init() method
		if self.auto_run:
			try:
				self.run()
			except (KeyboardInterrupt, SystemExit):
				print("Received keyboard interrupt.  Shutting down..")

	def loadConfig(self, configFile):
		
		# calculate application base name and real application path
		e = configFile.split("/")
		self.appFullName = e[len(e)-1]
		self.appBaseName = self.appFullName
		if "." in self.appBaseName:
			e = self.appBaseName.split('.')
			self.appBaseName = e[len(e)-2]
		self.appPath = os.path.dirname(os.path.realpath(configFile))
		
		self.stateCacheFile = os.path.join(self.appPath, "{0}.cache".format(self.appBaseName))
		
		if self.debugEnabled:
			print("sys.argv[0]: {0}".format(sys.argv[0]))
			print("realpath(sys.argv[0]): {0}".format(os.path.realpath(sys.argv[0])))
			print("dirname(realpath(sys.argv[0])): {0}".format(os.path.dirname(os.path.realpath(sys.argv[0]))))
	
			print("script full name: {0}".format(self.appFullName))
			print("script base name: {0}".format(self.appBaseName))
			print("script location: {0}".format(self.appPath))
			print("stateCacheFile: {0}".format(self.stateCacheFile))
		
		# Check for commandline arguments
		# Load config
		if (len(sys.argv) >= 2):
			
			# build a path from supplied argument accounting for
			# referencing local file versus remote file (./ vs full path /)
			self.configPath = sys.argv[1]
			if self.configPath[:2] != "./":
				self.configPath = os.path.join(self.appPath, self.configPath)

			# Supplied config path is not a real file or cannot be accessed	
			if not os.path.isfile(self.configPath):
				print("cannot access configuration file {0}".format(sys.argv[1]))
				exit()
		else:
			
			# build a default config file and path based on script base name
			self.configPath = os.path.join(self.appPath, "{0}.cfg".format(self.appBaseName))
			
			# the default config file does not exist or could not be accessed
			if not os.path.isfile(self.configPath):
				print("needs config; eg. {0}.cfg".format(self.appBaseName))
				exit()
			
		# Try to process config file
		try:
			with open(self.configPath) as data_file:
				self.config = json.load(data_file)
			print("loaded config from: {0}".format(self.configPath))
		except:
			self.writeLog("unable to process configuration file {0}".format(self.configPath))

	#
	# STUB METHODS for reimplementation 
	# in subclasses
	#
	def init():
		pass
		
	def setDigitalOutput(self, channel, value, quiet = False):
		return True
		
	def setDigitalInputPullup(self, channel, value):
		return True
		
	def pollInputs(self):
		pass
	

	def _onMqttConnect(self, *args, **kwargs):
		self.mqttc.subscribe("io/{0}/+/+/set/#".format(self.clientName), QOS_EXACTLY_ONCE)
		self.mqttc.publish("clients/{0}/status".format(self.clientName), 'online', QOS_AT_LEAST_ONCE, True)

	def _onMqttMessage(self, *args, **kwargs):

		# will it always be 2?
		msg = args[2]

		# dio-output set parameter
		# Valid Parameters:
		# state - set output state (on/off, etc)
		# mode - Set output mode, (open_collector, logic, etc)
		# pulse - Start pulse patten
		match = re.search("io/{0}/dio-output/([0-9]*)/set/([0-9A-Za-z]*)".format(self.clientName), msg.topic)
		if match:
		
			channel = int(match.group(1))
			message = msg.payload.decode("utf-8")
			
			if (channel < 0) or (channel >= self.num_dio_outputs):
				self.writeLog("specified channel ({0}) is not within range of 0-{1}".format(channel, (self.num_dio_outputs-1)), "error")

			if match.group(2).lower() == "state":
				self._setDigitalOutput(channel, message)
				if self.debugEnabled:
					print("set state ch {0} to {1}".format(channel, message))

			# Pulse output
			# Length of ON
			# Length of OFF
			# Repetitions
			# Time Off Between = 0
			elif match.group(2).lower() == "pulse":
				
				# Return if we do not have arguments
				if not len(message):
					self.writeLog("pulse command requires arguments \"{0}\"".format(msg.topic), "error")
					return True
				
				arguments = []
				if ',' in message: arguments = str(message).split(",")
				else: arguments.append(message)

				# Proceed with Pulse Call
				if not self.dioOutputPulse[channel].pulse(arguments):
					# Turn DIO Channel ON quietly
					self._setDigitalOutput(channel, 1, True)
				else:
					self.writeLog("failed to pulse output channel \"{0}\"; bad arguments".format(channel), "error")
			
			else:
				# error, unrecognized command
				self.writeLog("unrecognized command \"{0}\" -> \"{1}\" received; ignoring".format(msg.topic, message), "error")

		# dio-output pullup set
		match = re.search("io/{0}/dio-input/([0-9]*)/pullup/set/([0-9A-Za-z]*)".format(self.clientName), msg.topic)
		if match:

			if match.group(2).lower() == "pullup":
				self._setDigitalInputPullup(match.group(1), message)

		# dio-output set mode
		# gpio
		# open collector
		# tri-state

		# dio-output pulse

	# formerly _onMqttPublish(self, mosq, obj, mid):
	def _onMqttPublish(self, *args, **kwargs):
	    pass

	# formerly _onMqttSubscribe(self, mosq, obj, mid, granted_qos):
	def _onMqttSubscribe(self, *args, **kwargs):
	    pass

	def writeLog(self, message, level="debug"):
		self.mqttc.publish("log/{0}/{1}".format(self.clientName,level), message, QOS_AT_MOST_ONCE)

	def loadState(self):

		# init state first so we can append or otherwise
		# default if a state is not available to load
		self.initState()

		# check if stateCacheFile can be read
		if not os.path.isfile(self.stateCacheFile):
			return True

		try:
			with open("{0}/piface.cache".format(self.appPath)) as data_file:
				self.state = json.load(data_file)
				self.writeLog("loaded piface cached state from disk")
		except:
			self.writeLog("unable to process piface cached state ({0}/piface.cache)".format(self.appPath))
			return True

		# resume IO state and settins
		for i in range(len(self.state["outputs"])):
			# Quietly set Digital Outputs
			self.setDigitalOutput(i, self.state["outputs"][i]["state"], True)
		for i in range(len(self.state["inputs"])):
			self.setDigitalInputPullup(i, self.state["inputs"][i]["pullup"])
			# load cached input state; which will be 
			# checked immediately during the mainloop
			# this helps by creating events only for
			# inputs which have genuinely changed and will
			# keep noise down between process cycles
			self.state["inputs"][i]["state"] = self.state["inputs"][i]["state"]

		return False

	# Write state to disk / cache
	def writeStateCache(self):
		with open("{0}/piface.cache".format(self.appPath), 'w') as outfile:
			json.dump(self.state, outfile, indent=1)

	def initState(self):

		# Build state array
		self.state  = {}

		self.state["inputs"] = []
		for i in range(self.num_dio_inputs):
			
			input = {}
			self.state["inputs"].append(input)
			
			# default to false input state until checked later on
			self.state["inputs"][i]["state"] = 0
			
			# default to internal pullups enabled for all inputs
			# otherwise, unknowing users will be surprised with noise
			self.state["inputs"][i]["pullup"] = 1
			self.state["inputs"][i]["time_last_change"] = None

		self.state["outputs"] = []
		for i in range(self.num_dio_outputs):
			output = {}
			self.state["outputs"].append(output)
			self.state["outputs"][i]["state"] = 0

	def _setDigitalOutput(self, channel, value, quiet = False):

		# check that requested channel exists
		channel = int(channel)
		if (channel < 0) or (channel >= self.num_dio_outputs):
			# todo throw exception
			self.writeLog("channel of {0} does not match 0-{1}".format(channel,self.num_dio_outputs), "error")
			return True

		# substitute supplied value
		if (value == "on"): value = 1
		if (value == "off"): value = 0
		if (value == "high"): value = 1
		if (value == "low"): value = 0

		value = int(value)
		if not ((value == 1) or (value == 0)):
			# todo throw exception
			self.writeLog("value of {0} does not match 0 or 1".format(value), "error")
			return True

		# pass to another method which will often
		# be re-implemented in subclass
		if not self.setDigitalOutput(channel, value):

			# track, publish, and set state
			# cache state to disk
			if not quiet:
				self.state["outputs"][channel]["state"] = value
				self.mqttc.publish("io/{0}/dio-output/{1}/state".format(self.clientName, channel), value, QOS_AT_LEAST_ONCE, True)
				self.writeStateCache()


	def _setDigitalInputPullup(self, channel, value):

		# check that requested channel exists
		channel = int(channel)
		if (channel < 0) or (channel >= self.num_dio_inputs):
			# todo throw exception
			return True

		# substitute supplied value
		if (value == "on"): value = 1
		if (value == "off"): value = 0
		if (value == "high"): value = 1
		if (value == "low"): value = 0

		value = int(value)

		if not (value == 1) or (value == 0):
			self.writeLog("value of {0} does not match 0 or 1".format(value), "error")
			return True

		# pass to another method which will often
		# be re-implemented in subclass
		if not self.setDigitalInputPullup(channel, value):

			# track, publish, and set state
			# cache state to disk
			self.state["inputs"][channel]["pullup"] = value
			self.mqttc.publish("io/{0}/dio-input/{1}/pullup".format(self.clientName, channel), value, QOS_AT_LEAST_ONCE, True)

			self.writeStateCache()
		
	def _pollInputs(self):
		
		# time this io bank poll for performance
		if self.inputPollTimeMs is 0:
			timeStart = time.time()
		
		# Clear inputStateCheck list
		self.inputStateCheck = []
		
		# Call subclass method which should
		# fill inputStateCheck with checked values
		self.pollInputs()
		
		# Iterate list of checked inputs and check
		# against previous cached state for changes
		for i in range(len(self.inputStateCheck)):
			if self.state["inputs"][i]["state"] != self.inputStateCheck[i]:
				if self.debugEnabled:
					print("input ch{0} changed from {1} to {2}".format(i, self.inputStateCheck[i], self.state["inputs"][i]["state"]))
				self.state["inputs"][i]["state"] = self.inputStateCheck[i]
				self.mqttc.publish("io/{0}/dio-input/{1}/state".format(self.clientName, i), self.inputStateCheck[i], QOS_AT_LEAST_ONCE, True)
				# self.writeStateCache()
				
		if self.inputPollTimeMs is 0:
			self.inputPollTimeMs = (time.time() - timeStart) * 1000
			self.writeLog("input bank poll time is {:.2f} milliseconds".format(self.inputPollTimeMs), "debug")
	
	# digitalInputChanged(channel, new state, timestamp elapsed seconds)
	# Called from subclass, generally after an interrupt was
	# generated.  Could be called as a result of polling within
	# a subclass also
	def digitalInputChanged(self, channel, state, timestamp):
	
		# do we in fact have an input transition event	
		if self.state["inputs"][channel]["state"] != state:
			
			# build an event object
			event = {}
			event["value_new"] = state
			event["value_old"] = self.state["inputs"][channel]["state"]
			
			# calculate elapsed time since last transition event
			# convert to milliseconds and round to nearest whole millisecond
			if self.state["inputs"][channel]["time_last_change"] is not None:
				event["time_elapsed"] = round((time.time() - self.state["inputs"][channel]["time_last_change"]) * 1000)
				
			# timestamp current event
			event["time_event"] = time.time()
		
			if self.debugEnabled:
				print("input ch{0} changed from {1} to {2}".format(channel, self.state["inputs"][channel]["state"], state))
				
			self.state["inputs"][channel]["state"] = state
			self.mqttc.publish("io/{0}/dio-input/{1}/state".format(self.clientName, channel), state, QOS_AT_LEAST_ONCE, True)
			
			# determine event transition type
			if state: input_transition_direction = "rise"
			else: input_transition_direction = "fall"
			
			# send JSON event
			self.mqttc.publish("io/{0}/dio-input/{1}/event/transition/{2}".format(self.clientName, channel, input_transition_direction), json.dumps(event))
			
			# store this event for calculation of event duraction
			self.state["inputs"][channel]["time_last_change"] = time.time()

	def run(self):
		running = True
		loop_count = 0
		try:
			if self.debugEnabled:
				print("starting ::run() mainloop")
				
			while running:
				
				if self.digitalInputPollingEnabled:
					self._pollInputs()
				
				# Process Output Pulses
				for i in range(self.num_dio_outputs):
					if self.dioOutputPulse[i].process():
						self._setDigitalOutput(i, self.dioOutputPulse[i].outputRequest, True)
						self.dioOutputPulse[i].outputRequest = None
				
				# sleep during main loop unless it was
				# found that input bank polling takes 
				# longer than one msec
				if self.inputPollTimeMs > 1:
					time.sleep(0.001) # in mS
				
		except KeyboardInterrupt:
			self.writeStateCache()
			running = False




class distio_input():
	pass