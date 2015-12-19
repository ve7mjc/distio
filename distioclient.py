# distio client class
#

import sys, os
from fnmatch import fnmatch, fnmatchcase
import time
import socket
import re

import paho.mqtt.client as paho
import json, pprint

QOS_AT_MOST_ONCE = 0
QOS_AT_LEAST_ONCE = 1
QOS_EXACTLY_ONCE = 2

class DistIoClient():

	def __init__(self, config=None):

		# default hardware template
		self.num_dio_inputs = 0
		self.num_dio_outputs = 0
		self.num_adc_inputs = 0
		self.num_dac_outputs = 0
		self.debug_enabled = False

		self.auto_run = True

		# calculate application base name and real application path
		self.scriptNameBase = sys.argv[0]
		if "." in sys.argv[0]:
			e = sys.argv[0].split(".")
			self.scriptNameBase = e[len(e)-2]

		self.appPath = os.path.dirname(os.path.realpath(sys.argv[0]))
		self.stateCacheFile = "{0}/{1}.cache".format(self.appPath, self.scriptNameBase)

		# call init method which may be reimplemented
		self.init()

		# Check for commandline arguments
		# Load config
		if (len(sys.argv) < 2):
			# attempt to load from script_name.cache
			try:
				with open("{0}/{1}.json".format(self.appPath, self.scriptNameBase)) as data_file:
					self.config = json.load(data_file)
			except:
				print("needs config; eg. {0} config.json".format(sys.argv[0]))
				exit()
		else:
			# Check if config file supplied is accessible,
			# otherwise quit
			if not os.path.isfile(sys.argv[1]):
				print("cannot access {0}".format(sys.argv[1]))
				exit()

			# Load JSON configuration from disk
			try:
				with open(sys.argv[1]) as data_file:
					self.config = json.load(data_file)
			except:
				print("unable to process {0}".format(sys.argv[1]))
				exit()

		self.clientName = self.config["mqttClientName"]
		self.mqttc = paho.Client(self.clientName)

		# Assign event callbacks for MQTT client
		self.mqttc.on_message = self._onMqttMessage
		self.mqttc.on_connect = self._onMqttConnect
		self.mqttc.on_publish = self._onMqttPublish
		self.mqttc.on_subscribe = self._onMqttSubscribe

		# Set MQTT Last Will and Testament to maintain
		# client status tracking
		# maintaind during on_connect callback also
		if self.debug_enabled:
			print("Connecting to MQTT Broker at {0}:{1}".format(self.config["mqttRemoteHost"], self.config["mqttRemotePort"]))
		self.mqttc.will_set("clients/{0}/status".format(self.clientName), 'offline', QOS_AT_LEAST_ONCE, True)
		self.mqttc.connect(self.config["mqttRemoteHost"], self.config["mqttRemotePort"])
		self.mqttc.loop_start()

		# Initialize state and then attemp to recover
		# from a disk cache
		# todo, consider reloading state from a retained
		# MQTT topic message
		self.initState()
		self.loadState()

		# we are not yet resuming continuous pulsing
		# outputs from persistent state cache from disk
		self.inputStateCheck = []
		self.dioOutputPulse = []
		for i in range(self.num_dio_outputs):
			self.dioOutputPulse.append(Pulse())

		# automatically begin mainloop unless
		# directed otherwise in reimplemented init() method
		if self.auto_run: 
			self.run()

	def init():
		# this is a stub for subclassing
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
				if self.debug_enabled:
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

		# check if stateCacheFile can be read
		if not os.path.isfile(self.stateCacheFile):
			return True

		try:
			with open("{0}/piface.cache".format(self.appPath)) as data_file:
				self.state = json.load(data_file)
				self.writeLog("loaded piface cached state from disk")
		except:
			self.writeLog("unable to process piface cached state ({0}/piface.cache)".format(appPath))
			return True

		# resume IO state and settins
		for i in range(len(state["outputs"])):
			self.pfio.digital_write(i, state["outputs"][i]["state"])
		for i in range(len(state["inputs"])):
			self.pfio.digital_write_pullup(i, state["inputs"][i]["pullup"])
			self.state["inputs"][i]["state"] = self.pfio.digital_read(i)

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
			self.state["inputs"][i]["state"] = 0
			self.state["inputs"][i]["pullup"] = 0

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

	# return False on Success, True on Error
	def setDigitalOutput(self, channel, value, quiet = False):
		return True

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

	def setDigitalInputPullup(self, channel, value):
		return True

	def _pollInputs(self):
		self.inputStateCheck = []
		self.pollInputs()
		for i in range(len(self.inputStateCheck)):
			if self.state["inputs"][i]["state"] != self.inputStateCheck[i]:
				self.state["inputs"][i]["state"] = self.inputStateCheck[i]
				self.mqttc.publish("io/{0}/dio-input/{1}/state".format(self.clientName, i), inputStateCheck[i], QOS_AT_LEAST_ONCE, True)
				self.writeStateCache()

	def pollInputs(self):
		pass

	def run(self):
		running = True
		try:
			if self.debug_enabled:
				print("starting ::run() mainloop")
				
			while running:
				
				self._pollInputs()
				
				# Process Output Pulses
				for i in range(self.num_dio_outputs):
					if self.dioOutputPulse[i].process():
						self._setDigitalOutput(i, self.dioOutputPulse[i].outputRequest, True)
						self.dioOutputPulse[i].outputRequest = None
				
				time.sleep(0.01) # 10mS resolution
				
		except KeyboardInterrupt:
			self.writeStateCache()
			running = False


# Pulse State Machine
# 1 - On for xx ms, then off
# 2 - On for xx ms, Off for xx ms, repeat xx times
# 3 - On for xx ms, Off for xx ms, repeat xx times,
#     off for xx ms, repeat xx times
#     typical would be blink patterns on indicators
# Note: values are milliseconds and loop counts
#       a value of 0 indicates indefinite (may need to change)
#
class Pulse():

	def __init__(self):
		self.configured = False
		self.running = False
		self.outputRequest = None
		
		# how do we track where we are?
		# we are in a pulse, or an off pulse, or in between sets waiting

	def pulse(self, args):

		# process supplied arguments
		if len(args) > 0: self.on_time = int(args[0])
		if len(args) > 1: self.off_time = int(args[1])
		else: self.off_time = -1
		if len(args) > 2: self.num_reps = int(args[2])
		else: self.num_reps = -1
		if len(args) > 3: self.time_between_sets = int(args[3])
		else: self.time_between_sets = -1
		if len(args) > 4: self.num_sets = int(args[4])
		else: self.num_sets = -1

		self.on = False
		self.rep_count = 0
		self.rep_timer = self.on_time
		
		self.configured = True
		self.process()

		self.startTimer()
		
		self.running = True
		
		# States
		# 0 - in a pulse
		# 1 - in a pulse off_time
		# 2 - waiting in between sets
		self.state = 0
		self.currentRep = 1	
		self.currentSet = 1
		
		return False
		
	def startTimer(self):
		self.timer = time.time()
		
	def checkTimer(self):
		elapsedTime = (time.time() - self.timer) * 1000;
		return elapsedTime

	# advance time, process state
	def process(self):

		# return if not set up properly
		if not self.configured:
			return False
			
		if self.running:
			
			# Waiting in a pulse
			if self.state == 0:
				if self.checkTimer() > self.on_time:
					self.outputRequest = 0
					
					# if an off time has not been declared, we
					# are done here
					if self.off_time == -1:
						self.running = False
					else:
						self.state = 1
						self.startTimer()
					
			# Waiting after a pulse
			elif self.state == 1:
				
				if self.checkTimer() > self.off_time:
					
					# number of reps not specified but off time
					# was thus, we are looping indefinitely
					if (self.num_reps <= 0):
						self.startTimer()
						self.state = 0
						self.outputRequest = 1
					# we are tracking number of reps
					elif (self.num_reps > 0):
						if self.currentRep < self.num_reps:
							# go into another rep
							self.startTimer()
							self.currentRep = self.currentRep + 1
							self.state = 0
							self.outputRequest = 1
						else:
							# completed target number of reps
							# do we need to enter inter-rep-delay
							if self.time_between_sets >= 0:
								# waiting between reps
								self.state = 2
								self.startTimer()
							else:
								# concluded our reps
								self.running = False

			# Waiting in between sets
			elif self.state == 2:
				if self.checkTimer() > self.time_between_sets:
					
					# have we completed our sets?
					if (self.currentSet < self.num_sets) or (self.num_sets <= 0):
						# start a new rep in a new set
						self.currentRep = 1
						self.currentSet = self.currentSet + 1
						self.state = 0
						self.outputRequest = 1
						self.startTimer()
					else:
						# we are done
						self.running = False

		# If we require DIO maintenance,
		# flag this in the return
		if self.outputRequest is not None:
			#print("requesting transition to {0}".format(self.outputRequest))
			return True
		
		# work is not required
		return False
