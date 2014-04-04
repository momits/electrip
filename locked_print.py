#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
from Queue import Queue

def locked_print(*args):
    strings = map(str, args)
    string = " ".join(strings)
    print_lock.acquire()
    print string
    print_lock.release()

print_lock = threading.Lock()

class SocketThread(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        # we allow at most 20 unhandled srcp-commands at a time
        self.msg_queue = Queue(20)
        self.socket = socket
        
    def send_and_wait_for_answer(self, msg):
        self.msg_queue.put(msg, timeout=1)
#          self.socket.send(message)
#          locked_print(">> " + message)
#          self.wait_for_answer()
#         
    def wait_for_answer(self):
        ans = self.socket.recv(4096)
        if ans != "":
            locked_print("SRCP-INFO:", ans)
        
    def run(self):
        while True:
            msg = self.msg_queue.get()
            if msg == None:
                break
            self.socket.send(msg)
            locked_print(">> " + msg)
            self.wait_for_answer()
            self.msg_queue.task_done()
            
    def quit(self):
        self.msg_queue.put(None)
