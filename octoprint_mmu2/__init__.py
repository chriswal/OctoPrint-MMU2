# coding=utf-8
from __future__ import absolute_import

__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2019 chriswal - Released under terms of the AGPLv3 License"

from octoprint.settings import settings
from octoprint.server import user_permission
import octoprint.plugin
import serial
import json
import urllib2
import threading
import time

mmu2_ser = serial.Serial(port=None)
next_filament = ""
old_filament = ""
toolchange_detected = False



class MMU2Plugin(octoprint.plugin.StartupPlugin,
				octoprint.plugin.SettingsPlugin,
				octoprint.plugin.AssetPlugin,
				octoprint.plugin.TemplatePlugin,
				octoprint.plugin.ShutdownPlugin):


	def on_after_startup(self):
		self._logger.info("mmu2 plugin started")
		self._serialport=self._settings.get(["serialport"])
		self._baudrate=self._settings.get(["baudrate"])
		self._stoppbits=self._settings.get(["stoppbits"])
		self._bytesize=self._settings.get(["bytesize"])
		self._parity=self._settings.get(["parity"])
		self.reset_MMU2(self._serialport,self._baudrate)
		try:
			mmu2_ser = serial.Serial(
				port=self._serialport,
				baudrate=115200,
				timeout=0.5,
				write_timeout=0.5
				#parity=serial.PARITY_NONE,
				#stopbits=serial.STOPBITS_ONE,
				#bytesize=serial.EIGHTBITS
				)
		except ValueError:
			self._logger.error("serial port definition error")
		except serial.SerialException:
			self._logger.error("cannot open com port for mmu2")
		else:
			self._logger.info("serial port for mmu2 open")
			try:
				mmu2_ser.write("S0\n")
			except serial.SerialTimeoutException:
				self._logger.error("write timeout")
			else:
				self._logger.info("S0 data written")

			mmu2_ok = mmu2_ser.read(size=3)[0:-1]
			self._logger.info("Answer %s" % mmu2_ok)
			try:
				mmu2_ser.write("S1\n")
			except serial.SerialTimeoutException:
				self._logger.error("write timeout")
			else:
				self._logger.info("S1 data written")

			mmu2_firmware_version = mmu2_ser.read(size=6)[0:-3]
			self._logger.info("Answer %s" % mmu2_firmware_version)



	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(serialport="com9",
					baudrate="115200",
					stoppbits="0",
					bytesize="8",
					parity="None",
					timeout=30,
					mmu2commands=dict(
						okresponse="ok",
						checkpresent="S0",
						stopfeeding="A",
						filamentchange="T",
						loadfilament="L",
						mmu2mode="M",
						mmu2reset="X0",
						findastate="P0",
						filamenttype="F",
						mmu2firmwareversion="S1",
						mmu2buildnummer="S2",
						mmu2driveerror="S3",
						continueloading="C0",
						eject="E",
						recoveraftereject="R0",
						waitforuserclick="W0",
						cutfilament="K"
					)
		)

	##~~ AssetPlugin mixin

	def get_assets(self):
		# Define your plugin's asset files to automatically include in the
		# core UI here.
		return dict(
			js=["js/mmu2.js"],
			css=["css/mmu2.css"],
			less=["less/mmu2.less"]
		)

	def get_template_configs(self):
		return [
			dict(type="navbar", custom_bindings=False),
			dict(type="settings", custom_bindings=False)
			]

	##~~ Softwareupdate hook

	def get_update_information(self):
		# Define the configuration for your plugin to use with the Software Update
		# Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
		# for details.
		return dict(
				mmu2=dict(
				displayName="MMU2 Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="chriswal",
				repo="OctoPrint-MMU2",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/chriswal/OctoPrint-MMU2/archive/{target_version}.zip"
			)
		)

	def on_shutdown(self):
		mmu2_ser.close()
		self._logger.info("serial port to MMU2 closed")

	def rewrite_T_command(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		self._logger.info("command queued %s" % cmd)
		if (gcode and cmd == "T0") or (gcode and cmd == "T1") or (gcode and cmd == "T2") or (gcode and cmd == "T3") or (gcode and cmd == "T4"):
			global old_filament
			global next_filament
			old_filament = next_filament
			next_filament = cmd[-1:]
			self._logger.info("toolchange detected %s" % next_filament)
			self._printer.set_job_on_hold(True)
			cmd = None
			global toolchange_detected
			toolchange_detected = True
			handle_tool_change = threading.Thread(target=self.handle_filament_change, args=())
			handle_tool_change.start()
		return cmd,

	def sent_pause(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		self._logger.info("command sent %s" % cmd)
		if gcode and cmd == "pause":
			self._logger.info("Just sent T: {cmd}".format(**locals()))

	def reset_MMU2(self,serialport,baudrate):
		port = self.open_serial_port(serialport,baudrate)
		self.send_MMU2_command(port,"X0")
		time.sleep(1)
		port.close()

	def send_MMU2_command(self,port,command):
		try:
			self._logger.info("Port used %s %d" % (port.name,port.baudrate))
			port.write(command+"\n")
		except serial.portNotOpenError:
			self._logger.error("Port not open to MMU2")
		except serial.SerialTimeoutException:
			self._logger.error("Write timeout to MMU2")
		else:
			self._logger.info("Command %s written to MMU2" % command)

	def open_serial_port(self,serialport,baudrate):
		try:
			mmu2_ser = serial.Serial(
				port=serialport,
				baudrate=baudrate,
				timeout=0.5,
				write_timeout=0.5
				#parity=serial.PARITY_NONE,
				#stopbits=serial.STOPBITS_ONE,
				#bytesize=serial.EIGHTBITS
				)
		except ValueError:
			self._logger.error("serial port definition error")
		except serial.SerialException:
			self._logger.error("cannot open com port for mmu2")
		else:
			self._logger.info("serial port for mmu2 open")
			return mmu2_ser

	def send_printer_command(self,cmd, tags):
		self._printer.commands(cmd, None)

	def handle_filament_change(self):
		self._logger.info("Filament change")
		self._printer.set_job_on_hold(False)
		#		self.send_printer_command("@resume", "None")


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MMU2Plugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.rewrite_T_command,
		"octoprint.comm.protocol.gcode.sent": __plugin_implementation__.sent_pause

	}

