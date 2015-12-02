#!/usr/bin/python

# manager for entire project or system
# manages subprocess and their dependencies
# monitors their health and availability
# can be controlled remotely
#

import subprocess
import threading
import Queue

import logging
import time

import os, urlparse
import paho.mqtt.client as paho

logging.basicConfig(level = logging.DEBUG,
	format = '(%(threadName)-15s) %(message)s',
		)

# class ServiceProcess(threading.Thread):

# 	def __init__(self, config):
# 		threading.Thread.__init__(self)
# 		pass

# 	def run(self):
# 		pass

# Service Handler
# Thread with associated process
class Service(threading.Thread):

	# careful, name is an actual thread class member
	
	def __init__(self, config):
		self.msgQ = Queue.Queue()
		self.config = config
		self._stop = threading.Event()
		self.processRunning = False
		self.processStarted = False
		threading.Thread.__init__(self)

	def startProcess(self):
		self.lastStartTime = time.time()
		self.process = subprocess.Popen(self.config["cmd"], shell=True)
		self.processRunning = True
		self.processStarted = True
		self.msgQ.put("running " + self.config["name"])

	def stopProcess(self):
		# we are abruptly terminating the process
		# we could come up with a better way to politely ask first
		self.processRunning = False
		self.processStarted = False
		
		# terminate process only if it has not already returned
		# especially if this is being called as part of a restart
		try:
			if self.process and not self.process.poll():
				self.process.terminate()
		except OSError:
			pass

	def run(self):

		self.startProcess()

		# detect that we have began execution of the process
		# but differentiate that it has not yet started
		# .. we could certainly block until it has began
		# or set a timer for some time

		while not self.stopped():

			# process.poll() returns None (False) when not exited
			# returns error code elsewise
			# since scripts ofter return (int)0, we must be specific
			# to look for anything BUT (NoneType)None
			if not self.process.poll() == None:
				# we have an exit
				self.processRunning = False
				#elf.msgQ.put(self.config["name"] + " exited unexpectedly")

			# waste cycles until the next loop
			time.sleep(0.05)

		print("exiting thread run()")

		return

	def stop(self):
		self.stopProcess()
		self._stop.set()

	def stopped(self):
		return self._stop.isSet()

	def restart(self):
		self.msgQ.put("restarting " + self.config["name"])
		self.stopProcess()
		self.startProcess()

## MQTT

# Define event callbacks
def on_connect(mosq, obj, rc):
	#mqttc.publish("logs/" + clientName + "/notice", "started overwatch")
	pass

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

def mqttcLog(message, level = "debug"):
	mqttc.publish("logs/" + clientName + "/" + level.lower(), message)

clientName = "overwatch"
mqttc = paho.Client(clientName)
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Parse CLOUDMQTT_URL (or fallback to localhost)
url_str = os.environ.get('CLOUDMQTT_URL', 'mqtt://172.23.2.5:1883')
url = urlparse.urlparse(url_str)

serviceThreads = [] # for tracking

serviceList = [] # tracking collection of services/modules
serviceList.append({"name" : "Security Agent", "cmd" : "python security.py"})
serviceList.append({"name" : "MQTT Dummy", "cmd" : "python dummy.py"})
serviceList.append({"name" : "MQTT Dummy", "cmd" : "python dummy.py"})
serviceList.append({"name" : "MQTT Dummy", "cmd" : "python dummy.py"})

# Initialize and begin MQTT
#mqttc.username_pw_set(url.username, url.password)
mqttc.will_set('clients/' + clientName, 'offline', 0, False)
mqttc.connect(url.hostname, url.port)

# Start up modules
for service in serviceList:
	t = Service(service)
	serviceThreads.append(t)
	t.start()

# we are now healthy
mqttc.publish("clients/" + clientName, 'healthy')

mqttc.loop_start()

# blocking loop with a KeyboardInterrupt exit
try:
	while True:

		for service in serviceThreads:
		
			# process thread born messages to 
			# pass to logging facility
			if not service.msgQ.empty():
				msg = service.msgQ.get(False)
				service.msgQ.task_done()
				mqttcLog(msg)

			# if process should be running but is not
			# lets restart it while being careful not to flap
			if service.processStarted and not service.processRunning:
				if ((time.time() - service.lastStartTime) > 1):
					service.restart()

		# sleep for 50ms
		time.sleep(0.05)

except KeyboardInterrupt:

	print("Received keyboard interrupt.  Shutting down..")

	for thread in serviceThreads:
		thread.stop()

	# exit non-forcefully
	mqttc.loop_stop(False)