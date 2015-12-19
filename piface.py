#!/usr/bin/python3

# Raspberry Pi PiFace Digital IO Adapter
# maps mqtt messages to piface commands and events
#
# Matthew Currie <matthew@ve7mjc.com>
# December 2015

import distioclient
import pifacedigitalio as pfio

class PiFaceAdapter(distioclient.DistIoClient):

	def init(self):
		self.num_dio_inputs = 8
		self.num_dio_outputs = 8
		pfio.init()

	def setDigitalOutput(self, channel, value):
		pfio.digital_write(channel, value)
		return False
		
	def setDigitalInputPullup(self, channel, value):
		pfio.digital_write_pullup(channel, value)
		return False

	def pollInputs(self):
		for i in range(self.num_dio_inputs):
			self.inputStateCheck.append(pfio.digital_read(i))

pi = PiFaceAdapter()