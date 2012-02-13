#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time

def locked_print(*args):
	strings = map(unicode, args)
	string = " ".join(strings)
	print_lock.acquire()
	print string
	print_lock.release()

print_lock = threading.Lock()

class SocketRecvThread(threading.Thread):
	def __init__(self, socket):
		threading.Thread.__init__(self)
		self.running = True
		self.socket = socket
		
	def run(self):
		while self.running:
			socket_news = self.socket.recv(4096)
			if socket_news != "":
				locked_print(socket_news)
			
	def quit(self):
		self.running = False

