import os, sys
import json

class config():
	
	def __init__(self):
		
		self.debugEnabled = False
		self.params = {}
		self.configured = False
	
	def param(self, *args):
		try:
			if len(args) == 1:
				if args[0] in self.params:
					return self.params[args[0]]
			if len(args) == 2:
				if args[0] in self.params:
					if args[1] in self.params[args[0]]:
						return self.params[args[0]][args[1]]
		except:
			pass
		return None

	# load json config file from supplied commandline
	# argument or from default config file name with
	# format of {app_path}/{app_base_name}.cfg
	def load(self, configFile=None):
		
		# TODO account for a configFile being
		# passed in
		
		# default to commandline arguments if a
		# filename is not supplied
		if configFile == None:
			pass
			
		# calculate application base name and real application path
		# uses system argument which is present regardless of
		# supplied arguments
		e = sys.argv[0].split("/")
		self.appFullName = e[len(e)-1]
		self.appBaseName = self.appFullName
		if "." in self.appBaseName:
			e = self.appBaseName.split('.')
			self.appBaseName = e[len(e)-2]
		self.appPath = os.path.dirname(os.path.realpath(self.appFullName))
		
		# default stateCacheFile path
		# format: {application_path}/{application_base_name}.cache
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
				self.params = json.load(data_file)
			print("loaded config from: {0}".format(self.configPath))
		except:
			print("unable to process configuration file {0}".format(self.configPath))
			print(sys.exc_info()[0])
			raise
		
		# Pass in the fruits of our path wrangling efforts
		self.params["appFullName"] = self.appFullName
		self.params["appBaseName"] = self.appBaseName
		self.params["appPath"] = self.appPath
		if "stateCacheFile" not in self.params:
			self.params["stateCacheFile"] = self.stateCacheFile

		self.configured = True
		return False