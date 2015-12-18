# distio client class
#

import sys, os
from fnmatch import fnmatch, fnmatchcase
import time
import socket
import re

import paho.mqtt.client as paho
import json, pprint

class DistIoClient():

	def __init__(self, config=None):

		# default hardware template
		self.num_dio_inputs = 0
		self.num_dio_outputs = 0
		self.num_adc_inputs = 0
		self.num_dac_outputs = 0
		
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
		receiver = MqttReceiver(self)
		self.mqttc.on_message = receiver.onMqttMessage
		self.mqttc.on_connect = receiver.onMqttConnect
		self.mqttc.on_publish = receiver.onMqttPublish
		self.mqttc.on_subscribe = receiver.onMqttSubscribe

		# Set MQTT Last Will and Testament to maintain
		# client status tracking
		# maintaind during on_connect callback also
		print("Connecting to MQTT Broker at {0}:{1}".format(self.config["mqttRemoteHost"], self.config["mqttRemotePort"]))
		self.mqttc.will_set("clients/{0}/status".format(self.clientName), 'offline', 1, True)
		self.mqttc.connect(self.config["mqttRemoteHost"], self.config["mqttRemotePort"])
		self.mqttc.loop_start()

		# what about the persistence cache?
		self.initState()
		self.inputStateCheck = []
		
		# automatically begin mainloop unless
		# directed otherwise in reimplemented init() method
		if self.auto_run: self.run()
		
	def init():
		pass

	# Define event callbacks
	# <__main__.PiFaceAdapter object at 0xca2a90>
	# <paho.mqtt.client.Client object at 0xca2b50>
	# None, 
	# {'session present': 0}, 
	# 0)
 	# self.on_connect(self, self._userdata, flags_dict, result
	def onMqttConnect(self):

		print("Connected to MQTT")
		self.mqttc.subscribe("io/{0}/#".format(self.clientName), 1)
		self.mqttc.publish("clients/{0}/status".format(self.clientName), 'online', 1, True)

	def onMqttMessage(self, client, mosq, obj, msg):

		# dio-output set value
		match = re.search("io/{0}/dio-output/([0-9A-Za-z]*)/set".format(self.clientName), msg.topic)
		if match:
			self._setDigitalOutput(match.group(1), msg.payload)

		# dio-output pullup set
		match = re.search("io/{0}/dio-input/([0-9A-Za-z]*)/pullup/set".format(self.clientName), msg.topic)
		if match:
			self._setDigitalInputPullup(match.group(1), msg.payload)
			
		# dio-output set mode
		# gpio
		# open collector
		# tri-state

		# dio-output pulse
		
		

	def onMqttPublish(self, mosq, obj, mid):
	    pass

	def onMqttSubscribe(self, mosq, obj, mid, granted_qos):
	    pass

	def writeLog(self, message, level="debug"):
		self.mqttc.publish("log/{0}/{1}".format(self.clientName,level), message)

	def loadState(self):

		if not os.path.isfile(self.stateCacheFile):
			return True

		try:
			with open("{0}/piface.cache".format(self.appPath)) as data_file:
				self.state = json.load(data_file)
				self.writeLog("loaded piface cached state from disk")
		except:
			self.writeLog("unable to process piface cached state ({0}/piface.cache)".format(appPath))
			return True

		# resume IO state and settinsg
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

	def _setDigitalOutput(self, channel, value):

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
			self.state["outputs"][channel]["state"] = value
			self.mqttc.publish("io/{0}/dio-output/{1}/state".format(self.clientName, channel), value, 1, True)
	
			self.writeStateCache()

	# return False on Success, True on Error		
	def setDigitalOutput(self, channel, value):
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
			self.mqttc.publish("io/{0}/dio-input/{1}/pullup".format(self.clientName, channel), value, 1, True)
	
			self.writeStateCache()
		
	def setDigitalInputPullup(self, channel, value):
		return True

	def _pollInputs(self):
		self.inputStateCheck = []
		self.pollInputs()
		for i in range(len(self.inputStateCheck)):
			if self.state["inputs"][i]["state"] != self.inputStateCheck[i]:
				self.state["inputs"][i]["state"] = self.inputStateCheck[i]
				self.mqttc.publish("io/{0}/dio-input/{1}/state".format(self.clientName, i), inputStateCheck[i], 2, True)
				self.writeStateCache()
				
	def pollInputs(self):
		pass
				
	# should re-declare this method
	def run(self):
		running = True
		try:
			while running:
				#self.mqttc.loop(timeout=0.01)
				self._pollInputs()
				time.sleep(0.1)
		except KeyboardInterrupt:
			self.writeStateCache()
			running = False

# Not sure why I need to buffer these callbacks
# with another class instance
# Could be threading related
# if not, python seems to flip/flop how many
# arguments are in the callback
class MqttReceiver:
	def __init__(self, client):
		self.client = client
		pass
		
	def onMqttConnect(self, mqttc, obj, flags, rc):
		self.client.onMqttConnect()

	def onMqttMessage(self, mqttc, obj, msg):
		print(msg.topic+" "+str(msg.qos)+" "+str(msg.payload))

	def onMqttPublish(self, mqttc, obj, mid):
		print("Published! "+str(mid))

	def onMqttSubscribe(self, mqttc, obj, mid, granted_qos):
		print("Subscribed! - "+str(mid)+" "+str(granted_qos))

	def onMqttLog(self, mqttc, obj, level, string):
		print(string)