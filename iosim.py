#!/usr/bin/python3

# iosim.py
# Distributed IO System
# Matthew Currie <matthew@ve7mjc.com> December 2015
#
# Simple IO adapter simulator
# subclass DistIoClient and re-implement a number of
# relevent methods to demonstrate a simple client
# subclass
#
# Requires iosim.json configuration or provide path
# to configuration via commandline argument

import distioclient

class IoSim(distioclient.DistIoClient):
	
	def init(self):
		self.num_dio_inputs = 8
		self.num_dio_outputs = 8
	
	def setDigitalOutput(self, channel, value, quiet = False):
		print("set_dio_output({0},{1})".format(channel, value))
		return false
	
	def pollInputs(self):
		# return nothing, which is fine
		# todo, add random bit flipping to create real
		# events to work with
		pass
			
sim = IoSim()
