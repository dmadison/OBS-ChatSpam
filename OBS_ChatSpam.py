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
import time


class TwitchIRC:
	def __init__(self, chan="", nick="", passw="", host="irc.twitch.tv", port=6667):
		self.channel = chan
		self.nickname = nick
		self.password = passw
		self.host = host
		self.port = port

		self.rate_num_msgs = 19  # Number of messages allowed...
		self.rate_timeframe = 30  # ...in timeframe of x seconds
		self.__message_timestamps = []

		self.__connected = False
		self.__last_message = None  # Last connection timestamp
		self.timeout = 10.0  # Time before open connection is closed, in seconds

		self.__sock = socket.socket()

	def connect(self, suppress_warnings=True):
		connection_result = self.__connect()

		if connection_result is not True:
			self.__connected = False
			if suppress_warnings:
				print("Connection Error:", connection_result)
				return False
			else:
				raise UserWarning(connection_result)

		self.__connected = True
		return True

	def __connect(self):
		if self.__connected:
			return True  # Already connected, nothing to see here

		self.__sock = socket.socket()
		self.__sock.settimeout(1)  # One second to connect

		try:
			self.__sock.connect((self.host, self.port))
		except socket.gaierror:
			return "Cannot find server"
		except (TimeoutError, socket.timeout):
			return "No response from server (connection timed out)"

		if self.password is not "":
			self.__sock.send("PASS {}\r\n".format(self.password).encode("utf-8"))
		self.__sock.send("NICK {}\r\n".format(self.nickname).encode("utf-8"))
		self.__sock.send("JOIN #{}\r\n".format(self.channel).encode("utf-8"))

		auth_response = self.read()
		if "Welcome, GLHF!" not in auth_response:
			return "Bad Authentication! Check your Oauth key"

		try:
			self.read()  # Wait for "JOIN" response
		except socket.timeout:
			return "Channel not found!"

		return True

	def disconnect(self):
		self.__sock.shutdown(socket.SHUT_RDWR)
		self.__sock.close()
		self.__connected = False

	def connection_timeout(self):
		if self.__connected and time.time() >= self.__last_message + self.timeout:
			self.disconnect()

	def test_authentication(self):
		if self.connect(False):
			self.disconnect()
		print("Authentication successful!")

	def chat(self, msg):
		# (So long as this function is only accessed via "ChatMessage", this check is redundant)
		# (Note: Checked in 'ChatMessage' to avoid spamming authentication)
		#if not self.check_rates():
		#	return  # Sending messages too fast!

		message_time = time.time()
		self.__message_timestamps.append(message_time + self.rate_timeframe)
		self.__last_message = message_time

		self.__sock.send("PRIVMSG #{} :{}\r\n".format(self.channel, msg).encode("utf-8"))
		print("Sent \'" + msg + "\'", "as", self.nickname, "in #" + self.channel)

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

	def check_rates(self):
		index = 0

		# Remove timestamps that have passed
		for index, timestamp in enumerate(self.__message_timestamps):
			if time.time() <= timestamp:
				break
		self.__message_timestamps = self.__message_timestamps[index:]

		# If at max rate, throw an error
		if len(self.__message_timestamps) >= self.rate_num_msgs:
			next_clear = int(self.__message_timestamps[0] - time.time())
			msg_plural = "s"

			if next_clear <= 1:
				next_clear = 1  # Avoiding "wait 0 more seconds" messages
				msg_plural = ""

			print("Error: Rate limit reached. Please wait " + str(next_clear) + " more second" + msg_plural)
			return False

		return True

twitch = TwitchIRC()

class ChatMessage:
	messages = []
	max_description_length = 32

	def __init__(self, msg, position, obs_settings, irc=twitch):
		self.text = msg
		self.irc = irc

		self.obs_data = obs_settings

		self.position = position
		self.hotkey_id = obs.OBS_INVALID_HOTKEY_ID
		self.hotkey_saved_key = None

		self.load_hotkey()
		self.register_hotkey()
		self.save_hotkey()

	def __del__(self):
		self.cleanup()

	def cleanup(self):
		self.deregister_hotkey()
		self.release_memory()

	def release_memory(self):
		obs.obs_data_array_release(self.hotkey_saved_key)

	def new_text(self, msg):
		self.text = msg
		self.deregister_hotkey()
		self.register_hotkey()

	def new_position(self, pos):
		self.deregister_hotkey()
		self.unsave_hotkey()
		self.position = pos
		self.register_hotkey()

	def load_hotkey(self):
		self.hotkey_saved_key = obs.obs_data_get_array(self.obs_data, "chat_hotkey_" + str(self.position))

	def register_hotkey(self):
		if len(self.text) > ChatMessage.max_description_length:
			key_description = self.text[:ChatMessage.max_description_length - 3] + "..."
		else:
			key_description = self.text
		key_description = "Chat \'" + key_description + "\'"

		self.callback = lambda pressed: self.key_passthrough(pressed)  # Small hack to get around the callback signature reqs.
		self.hotkey_id = obs.obs_hotkey_register_frontend("chat_hotkey", key_description, self.callback)
		obs.obs_hotkey_load(self.hotkey_id, self.hotkey_saved_key)

	def deregister_hotkey(self):
		obs.obs_hotkey_unregister(self.callback)

	def save_hotkey(self):
		self.hotkey_saved_key = obs.obs_hotkey_save(self.hotkey_id)
		obs.obs_data_set_array(self.obs_data, "chat_hotkey_" + str(self.position), self.hotkey_saved_key)

	def unsave_hotkey(self):
		obs.obs_data_erase(self.obs_data, "chat_hotkey_" + str(self.position))

	def key_passthrough(self, pressed):
		if pressed:
			self.send()

	def send(self, suppress_warnings=True):
		if not self.irc.check_rates():
			return  # Sending messages too fast!

		if self.irc.connect(suppress_warnings):
			self.irc.chat(self.text)

	@staticmethod
	def check_messages(new_msgs, settings):
		# Check if list hasn't changed
		if len(new_msgs) == len(ChatMessage.messages):
			num_diff = 0
			diff_index = None

			for index, msg in enumerate(ChatMessage.messages):
				if new_msgs[index] != msg.text:
					num_diff += 1
					diff_index = index
					if num_diff > 1:
						break
			else:
				if num_diff != 0:
					ChatMessage.messages[diff_index].new_text(new_msgs[diff_index])  # single entry modified
				return  # Lists identical

		# Check if objects already exist, otherwise create them
		new_list = []
		for pos, msg in enumerate(new_msgs):
			for msg_obj in ChatMessage.messages:
				if msg == msg_obj.text:
					new_list.append(msg_obj)
					break
			else:
				new_list.append(ChatMessage(msg, pos, settings))

		# Clean up old objects
		for msg in ChatMessage.messages:
			for msg_new in new_msgs:
				if msg.text == msg_new:
					break
			else:
				msg.cleanup()
				msg.unsave_hotkey()

		# Assign to master array and reindex
		ChatMessage.messages = new_list
		ChatMessage.__reindex_messages()

	@staticmethod
	def __reindex_messages():
		for index, msg in enumerate(ChatMessage.messages):
			msg.new_position(index)

		for msg in ChatMessage.messages:  # Separate loop as to avoid memory overwrites
			msg.save_hotkey()


# ------------------------------------------------------------

# OBS Script Functions

def check_connection():
	twitch.connection_timeout()

def test_authentication(prop, props):
	twitch.test_authentication()

def test_message(prop, props):
	ChatMessage.messages[0].send(False)

def script_description():
	return "<b>Twitch Chat Spam</b>" + \
			"<hr>" + \
			"Python script for sending messages to Twitch chat using OBS hotkeys." + \
			"<br/><br/>" + \
			"Made by David Madison" + \
			"<br/>" + \
			"www.partsnotincluded.com"

def script_update(settings):
	twitch.channel = obs.obs_data_get_string(settings, "channel").lower()
	twitch.nickname = obs.obs_data_get_string(settings, "user").lower()
	twitch.password = obs.obs_data_get_string(settings, "oauth").lower()

	obs_messages = obs.obs_data_get_array(settings, "messages")
	num_messages = obs.obs_data_array_count(obs_messages)

	messages = []
	for i in range(num_messages):  # Convert C array to Python list
		message_object = obs.obs_data_array_item(obs_messages, i)
		messages.append(obs.obs_data_get_string(message_object, "value"))

	ChatMessage.check_messages(messages, settings)
	obs.obs_data_array_release(obs_messages)

	#print("Settings JSON", obs.obs_data_get_json(settings))

def script_properties():
	props = obs.obs_properties_create()

	obs.obs_properties_add_text(props, "channel", "Channel", obs.OBS_TEXT_DEFAULT)
	obs.obs_properties_add_text(props, "user", "User", obs.OBS_TEXT_DEFAULT)
	obs.obs_properties_add_text(props, "oauth", "Oauth", obs.OBS_TEXT_PASSWORD)

	obs.obs_properties_add_editable_list(props, "messages", "Messages", obs.OBS_EDITABLE_LIST_TYPE_STRINGS, "", "")
	obs.obs_properties_add_button(props, "test_auth", "Test Authentication", test_authentication)
	obs.obs_properties_add_button(props, "test_message", "Test Message #1", test_message)

	return props

def script_save(settings):
	for message in ChatMessage.messages:
		message.save_hotkey()

def script_load(settings):
	obs.timer_add(check_connection, 1000)  # Check for timeout every second

def script_unload():
	obs.timer_remove(check_connection)

	for message in ChatMessage.messages:
		message.cleanup()
