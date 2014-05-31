#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import Queue
from socket import timeout

def locked_print(*args):
    """
    Acquires ``print_lock`` and then prints
    like the normal print-statement. Calling
    this method consequently ensures nice output
    when multiple threads are printing.
    """
    strings = map(str, args)
    string = " ".join(strings)
    print_lock.acquire()
    print string
    print_lock.release()

print_lock = threading.Lock()

class SocketThread(threading.Thread):
    """
    Thread implementing strictly sequential socket-
    communication from a client-perspective:
    It sends commands and the other side (the server) has
    to reply with information about its new state or errors.
    Provides (non-)blocking methods to add commands to the
    internal queue, the reply will be printed as soon as it
    was received using :func:`locked_print`.
    Prints error messages if more than 20 unanswered
    commands are pending in the queue or *timeout* is
    reached.
    """
    def __init__(self, socket, timeout=2):
        threading.Thread.__init__(self)
        # we allow at most 20 unhandled srcp-commands at a time
        self.msg_queue = Queue.Queue(20)
        self.socket = socket
        # two seconds without response raise a timeout-error
        socket.settimeout(timeout)
    
    def send_and_wait_for_answer(self, cmd):
        """
        Non-blocking method which adds *cmd* to the queue
        of commands to be sent to the server.
        """
        try:
            self.msg_queue.put(cmd, False)
        except Queue.Full:
            locked_print("Socket-Fehler: Mehr als 20 unbeantwortete Befehle.")
    
    def send_and_block_for_answer(self, cmd):
        """
        Blocking method which sends *cmd*, waits for the
        answer and then prints out both in a pretty format.
        """
        try:
            self.socket.send(cmd)
        except timeout:
            locked_print("Zeitüberschreitung beim "
                         "Senden des Befehls:\n" + cmd)
        else:
            locked_print("SEND>>: " + cmd,
                         "RECV<<:" + self.wait_for_answer())
    
    def wait_for_answer(self):
        """
        Blocks for a server-reply until
        the timeout is reached.
        """
        try:
            ans = self.socket.recv(4096)
        except timeout:
            return "Zeitüberschreitung der Server-Antwort."
        else:
            return ans
    
    def run(self):
        while True:
            msg = self.msg_queue.get()
            if msg == None:
                break
            try:
                self.socket.send(msg)
            except timeout:
                locked_print("Zeitüberschreitung beim "
                             "Senden des Befehls:\n" + msg)
            else:
                locked_print("SEND>>: " + msg,
                             "RECV<<:" + self.wait_for_answer())
            self.msg_queue.task_done()
    
    def quit(self):
        self.msg_queue.put(None)
