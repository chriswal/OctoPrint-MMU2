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


class MMU2Plugin(octoprint.plugin.StartupPlugin,
				octoprint.plugin.SettingsPlugin,
				octoprint.plugin.AssetPlugin,
				octoprint.plugin.TemplatePlugin,
				octoprint.plugin.ShutdownPlugin):


	def __init__(self):
		self.mmu2_ser = serial.Serial(port=None)
		self.old_filament = ""
		self.next_filament = ""
		self.absolute_coordinates = None
		self.extruder_absolute_coordinates = None
		self.timeout = 0
		self.erhtime = 0

	def on_after_startup(self):
		self._logger.info("mmu2 plugin started")
		self._serialport=self._settings.get(["serialport"])
		self._baudrate=self._settings.get(["baudrate"])
		self._timeout=self._settings.get(["timeout"])
		self._erhtime=self._settings.get(["erhtime"])
		self._stoppbits=self._settings.get(["stoppbits"])
		self._bytesize=self._settings.get(["bytesize"])
		self._parity=self._settings.get(["parity"])
		self._grabfilament=self._settings.get(["grabfilament"])
		self._feedtonozzle=self._settings.get(["feedtonozzle"])
		self.reset_MMU2(self._serialport, self._baudrate)
		self.timeout = float(self._timeout)
		self.erhtime = float(self._erhtime)
		try:
			self.mmu2_ser = serial.Serial(
				port=self._serialport,
				baudrate=115200,
				timeout=float(self._timeout),
				write_timeout=0.5
				#parity=serial.PARITY_NONE,
				#stopbits=serial.STOPBITS_ONE,
				#bytesize=serial.EIGHTBITS
				)
		except ValueError:
			self._logger.error("serial port definition error %s %s %s" % (self._serialport, self._baudrate, self._timeout))
		except serial.SerialException:
			self._logger.error("cannot open com port for mmu2")
		else:
			self._logger.info("serial port for mmu2 open")
			try:
				self.mmu2_ser.write("S0\n")
			except serial.SerialTimeoutException:
				self._logger.error("write timeout")
			else:
				self._logger.info("S0 data written")

			mmu2_ok = self.mmu2_ser.read(size=3)[0:-1]
			self._logger.info("Answer %s" % mmu2_ok)
			try:
				self.mmu2_ser.write("S1\n")
			except serial.SerialTimeoutException:
				self._logger.error("write timeout")
			else:
				self._logger.info("S1 data written")

			mmu2_firmware_version = self.mmu2_ser.read(size=6)[0:-3]
			self._logger.info("Answer %s" % mmu2_firmware_version)
		self.mmu2_ser.close()



	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(serialport="",
					baudrate="115200",
					stoppbits="0",
					bytesize="8",
					parity="None",
					timeout=60.1,
					grablength="5",
					grabspeed="300",
					unloadlength="12",
					unloadspeed="300",
					lengthtonozzle="40",
					erhtime=30,
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
		self.mmu2_ser.close()
		self._logger.info("serial port to MMU2 closed")

	def rewrite_mmu_command(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
		self._logger.info("command queued %s" % cmd)
		if (gcode and cmd == "T0") or (gcode and cmd == "T1") or (gcode and cmd == "T2") or (gcode and cmd == "T3") or (gcode and cmd == "T4"):
			self.old_filament = self.next_filament
			self.next_filament = cmd[-1:]
			cmd = None
			if self.old_filament != self.next_filament:
				self._logger.info("toolchange detected %s" % self.next_filament)
				self._printer.set_job_on_hold(True)
				self.mmu2_ser = self.open_serial_port(self._settings.get(["serialport"]), self._settings.get(["baudrate"]),
												self._settings.get(["timeout"]))
				handle_tool_change = threading.Thread(target=self.handle_filament_change, args=(self.mmu2_ser,))
				handle_tool_change.start()
		elif gcode and cmd == "M702 C":
			self._logger.info("unload detected")
			self._printer.set_job_on_hold(True)
			cmd = None
			self.old_filament = None
			self.mmu2_ser = self.open_serial_port(self._settings.get(["serialport"]), self._settings.get(["baudrate"]),
											self._settings.get(["timeout"]))
			handle_filament_unload = threading.Thread(target=self.handle_filament_unload, args=(self.mmu2_ser,))
			handle_filament_unload.start()
		elif gcode and cmd == "G90":
			self.absolute_coordinates = True
		elif gcode and cmd == "G91":
			self.absolute_coordinates = False
		elif gcode and cmd == "M82":
			self.extruder_absolute_coordinates = True
		elif gcode and cmd == "M83":
			self.extruder_absolute_coordinates = False
		return cmd,

	def init_mmu2_before_print(self,comm, script_type, script_name, *args, **kwargs):
		if not script_type == "gcode" or not script_name == "beforePrintStarted":
			return None
		else:
			self._logger.info("print started")
			self._logger.info("init mmu2 before print job")
			self._printer.set_job_on_hold(True)
			init_mmu2_thread = threading.Thread(target=self.init_mmu2, args=())
			init_mmu2_thread.start()
			return None

	def init_mmu2(self):
		self.reset_MMU2(self._settings.get(["serialport"]), self._settings.get(["baudrate"]))
		self.old_filament = ""
		self.next_filament = ""
		self.absolute_coordinates = None
		self.extruder_absolute_coordinates = None
		self._printer.set_job_on_hold(False)


	def reset_MMU2(self,serialport, baudrate, timeout=0):
		port = self.open_serial_port(serialport, baudrate, timeout)
		if port:
			self.send_MMU2_command(port, "X0")
			time.sleep(1)
			port.close()

	def send_MMU2_command(self, port, command):
		try:
			self._logger.info("Port used %s %d" % (port.name, port.baudrate))
			port.write(command+"\n")
		except serial.portNotOpenError:
			self._logger.error("Port not open to MMU2")
		except serial.SerialTimeoutException:
			self._logger.error("Write timeout to MMU2")
		else:
			self._logger.info("Command %s written to MMU2" % command)

	def open_serial_port(self, serialport, baudrate, timeout):
		try:
			self.mmu2_ser = serial.Serial(
				port=serialport,
				baudrate=float(baudrate),
				timeout=float(timeout),
				write_timeout=0.5
				#parity=serial.PARITY_NONE,
				#stopbits=serial.STOPBITS_ONE,
				#bytesize=serial.EIGHTBITS
				)
		except ValueError:
			self._logger.error("serial port definition error %s " % serialport)
		except serial.SerialException:
			self._logger.error("cannot open com port for mmu2")
		else:
			self._logger.info("serial port for mmu2 open")
			return self.mmu2_ser

	def send_printer_command(self, cmd, tags):
		self._printer.commands(cmd, None)

	def flush_ser_buffer(self, port, timeout):
		port.reset_input_buffer()
		port.reset_output_buffer()

	def wait_for_ok(self, port, timeout):
		mmu2_ok = False
		answer = port.read(size=3)[0:-1]
		if answer == "ok":
			mmu2_ok = True
		self._logger.info("Answer %s" % answer)
		return mmu2_ok

	def handle_filament_change(self, port):
		self._logger.info("Filament change")
		self.flush_ser_buffer(port, 0)
		if self.absolute_coordinates and self.extruder_absolute_coordinates is None:
			coordinate_cmd_before = "G91"
			coordinate_cmd_after = "G90"
		elif self.extruder_absolute_coordinates:
			coordinate_cmd_before = "M83"
			coordinate_cmd_after = "M82"
		elif not self.extruder_absolute_coordinates:
			coordinate_cmd_before = "M83"
			coordinate_cmd_after = "M83"
		else:
			coordinate_cmd_before = "G91"
			coordinate_cmd_after = "G91"
		self.send_printer_command((coordinate_cmd_before, "G1 E-30 F300", coordinate_cmd_after), None)
		self.send_MMU2_command(port, ("T"+self.next_filament).encode("UTF8"))
		ok = False
		i = (self.erhtime*60)/self.timeout
		while not ok or i < 0:
			i -= 1
			ok = self.wait_for_ok(port, 20)
		self.send_MMU2_command(port, "C0".encode("UTF8"))
		ok = False
		self.send_printer_command((coordinate_cmd_before, "G1 E5 F300", coordinate_cmd_after), None)
		time.sleep(1)
		self.send_MMU2_command(port, "A".encode("UTF8"))
		ok = self.wait_for_ok(port, 20)
		self.mmu2_ser.close()
		self._printer.set_job_on_hold(False)

	def handle_filament_unload(self, port):
		self._logger.info("Filament unload")
		self.flush_ser_buffer(port, 0)
		if self.absolute_coordinates and self.extruder_absolute_coordinates is None:
			coordinate_cmd_before = "G91"
			coordinate_cmd_after = "G90"
		elif self.extruder_absolute_coordinates:
			coordinate_cmd_before = "M83"
			coordinate_cmd_after = "M82"
		elif not self.extruder_absolute_coordinates:
			coordinate_cmd_before = "M83"
			coordinate_cmd_after = "M83"
		else:
			coordinate_cmd_before = "G91"
			coordinate_cmd_after = "G91"
		self.send_printer_command((coordinate_cmd_before, "G1 E-30 F300", coordinate_cmd_after), None)
		self.send_MMU2_command(port, "U0".encode("UTF8"))
		ok = False
		ok = self.wait_for_ok(port, 20)
		self.mmu2_ser.close()
		self._printer.set_job_on_hold(False)


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MMU2Plugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
		"octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.rewrite_mmu_command,
		"octoprint.comm.protocol.scripts": __plugin_implementation__.init_mmu2_before_print
	}

