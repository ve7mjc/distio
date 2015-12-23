# Pulse State Machine
# 1 - On for xx ms, then off
# 2 - On for xx ms, Off for xx ms, repeat xx times
# 3 - On for xx ms, Off for xx ms, repeat xx times,
#     off for xx ms, repeat xx times
#     typical would be blink patterns on indicators
# Note: values are milliseconds and loop counts
#       a value of 0 indicates indefinite (may need to change)
#

import time

class distio_pulse():

	def __init__(self):
		
		self.configured = False
		self.running = False
		self.outputRequest = None

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