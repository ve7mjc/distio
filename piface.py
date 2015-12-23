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

class PiFaceAdapter(distio_client):

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

	# Poll Digital Inputs
	# Can be disabled by setting 
	# self.digitalInputPollingEnabled to False
	# Performance: determined through loop testing that 
	# each digital_read takes 1.3 mS on average to poll
	def pollInputs(self):
		for i in range(self.num_dio_inputs):
			self.inputStateCheck.append(self.pfd.input_pins[i].value)
		pass

	def digitalInputInterrupt(self, event):
		self.digitalInputChanged(event.pin_num, event.direction, event.timestamp)

pi = PiFaceAdapter()
