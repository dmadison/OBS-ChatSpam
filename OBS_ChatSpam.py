#
# Project     OBS Twitch Chat Spam Script
# @author     David Madison
# @link       github.com/dmadison/OBS-ChatSpam
# @license    GPLv3 - Copyright (c) 2018 David Madison
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import obspython as obs
import socket
from time import sleep


class TwitchIRC:
	def __init__(self, chan="", nick="", passw="", host="irc.twitch.tv", port=6667):
		self.channel = chan
		self.nickname = nick
		self.password = passw
		self.host = host
		self.port = port
		self.max_rate = 20/30

		self.__sock = socket.socket()

	def connect(self):
		self.__sock = socket.socket()
		self.__sock.connect((self.host, self.port))
		if self.password is not "":
			self.__sock.send("PASS {}\r\n".format(self.password).encode("utf-8"))
		self.__sock.send("NICK {}\r\n".format(self.nickname).encode("utf-8"))
		self.__sock.send("JOIN #{}\r\n".format(self.channel).encode("utf-8"))

		auth_response = self.read()

		if "Welcome, GLHF!" not in auth_response:
			raise UserWarning("Authentication Error!")

	def disconnect(self):
		self.__sock.shutdown(socket.SHUT_RDWR)
		self.__sock.close()

	def chat(self, msg):
		self.__sock.send("PRIVMSG #{} :{}\r\n".format(self.channel, msg).encode("utf-8"))
		print("Sent \'" + msg + "\'", "as", self.nickname, "in #" + self.channel)
		sleep(self.max_rate)  # Simple way to avoid the rate limit

	def read(self):
		response = self.__read_socket()
		while self.__ping(response):
			response = self.__read_socket()
		return response.rstrip()

	def __read_socket(self):
		return self.__sock.recv(1024).decode("utf-8")

	def __ping(self, msg):
		if msg[:4] == "PING":
			self.__pong(msg[4:])
			return True
		return False

	def __pong(self, host):
		self.__sock.send(("PONG" + host).encode("utf-8"))

# ------------------------------------------------------------

# Global Vars
chat_text = ""
hotkey_id = obs.OBS_INVALID_HOTKEY_ID
twitch = TwitchIRC()

def chat(pressed):
	if pressed:
		twitch.connect()
		twitch.chat(chat_text)
		twitch.disconnect()

def test_pressed(props, prop):
	print("Testing chat spam script...")
	chat(True)

# ------------------------------------------------------------

# OBS Script Functions

def script_description():
	return "<b>Twitch Chat Spam</b>" + \
			"<hr>" + \
			"Python script for sending messages to Twitch chat using OBS hotkeys." + \
			"<br/><br/>" + \
			"Made by David Madison" + \
			"<br/>" + \
			"www.partsnotincluded.com"

def script_update(settings):
	global chat_text

	twitch.channel = obs.obs_data_get_string(settings, "channel").lower()
	twitch.nickname = obs.obs_data_get_string(settings, "user").lower()
	twitch.password = obs.obs_data_get_string(settings, "oauth").lower()
	chat_text = obs.obs_data_get_string(settings, "chat_text")

def script_properties():
	props = obs.obs_properties_create()

	obs.obs_properties_add_text(props, "channel", "Channel", obs.OBS_TEXT_DEFAULT)
	obs.obs_properties_add_text(props, "user", "User", obs.OBS_TEXT_DEFAULT)
	obs.obs_properties_add_text(props, "oauth", "Oauth", obs.OBS_TEXT_PASSWORD)
	obs.obs_properties_add_text(props, "chat_text", "Chat Text", obs.OBS_TEXT_MULTILINE)

	obs.obs_properties_add_button(props, "test_button", "Test", test_pressed)

	return props

def script_load(settings):
	global hotkey_id

	hotkey_id = obs.obs_hotkey_register_frontend("twitch_chat_hotkey", "Twitch Chat Hotkey", chat)
	hotkey_saved_key = obs.obs_data_get_array(settings, "twitch_chat_hotkey")
	obs.obs_hotkey_load(hotkey_id, hotkey_saved_key)

def script_save(settings):
	hotkey_saved_key = obs.obs_hotkey_save(hotkey_id)
	obs.obs_data_set_array(settings, "twitch_chat_hotkey", hotkey_saved_key)
	obs.obs_data_array_release(hotkey_saved_key)

def script_unload():
	obs.obs_hotkey_unregister(chat)
