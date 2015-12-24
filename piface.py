#!/usr/bin/python3

# Raspberry Pi PiFace Digital IO Adapter
# maps mqtt messages to piface commands and events
#
# Matthew Currie <matthew@ve7mjc.com>
# December 2015
#
# REMEMBER: Linux user permissions
#           User executing this script must be in spi,gpio,
#           and other groups
#

from distio_client import *
import pifacedigitalio

class piface_adapter(distio_client):

	def init(self):

		self.num_dio_inputs = 8
		self.num_dio_outputs = 8
		self.digitalInputPollingEnabled = False
		
		# debounce
		# could add code for debounce per input if needed
		self.debounceTimeSecs = 0.10
		
		self.pfd =  pifacedigitalio.PiFaceDigital()

		# Create listener and attach event for each input
		self.listener = pifacedigitalio.InputEventListener(chip=self.pfd)
		
	def start(self):
		
		# Create interrupt callbacks for all inputs
		# in both directions (rising and falling) with a
		# debounce or settle timer, and active the 
		# listerner thread
		for i in range(self.num_dio_inputs):
			self.listener.register(i, pifacedigitalio.IODIR_BOTH, self.digitalInputInterrupt, self.debounceTimeSecs)
		self.listener.activate()

	def setDigitalOutput(self, channel, value, quiet = False):
		self.pfd.output_pins[channel].value = value
		return False

	def setDigitalInputPullup(self, channel, value):
		self.pfd.gppub.bits[channel].value = value
		return False
		
	def readDigitalInput(self, channel):
		if (channel >= 0) and (channel < self.num_dio_inputs):
			return self.pfd.input_pins[channel].value
		else:
			self.writeLog("attempt to read digital input ({0}) outside of range({1})".format(channel, self.num_dio_inputs))

	def digitalInputInterrupt(self, event):
		self.digitalInputChanged(event.pin_num, event.direction, event.timestamp)

pi = piface_adapter()
