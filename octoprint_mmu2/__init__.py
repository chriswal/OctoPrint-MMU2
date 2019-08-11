# coding=utf-8
from __future__ import absolute_import


import octoprint.plugin

class MMU2Plugin(octoprint.plugin.SettingsPlugin,
                 octoprint.plugin.AssetPlugin,
                 octoprint.plugin.TemplatePlugin,
                 octoprint.plugin.StartupPlugin):

    def on_after_startup(self):
        self._logger.info("Hello World!")

	##~~ SettingsPlugin mixin

	def get_settings_defaults(self):
		return dict(
			# put your plugin's default settings here
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



def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = MMU2Plugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

