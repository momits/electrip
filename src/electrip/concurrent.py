#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import threading
import queue
from socket import timeout

logger = logging.getLogger(__name__)


class SRCPSocketThread(threading.Thread):
    """
    Thread implementing strictly sequential socket-
    communication from a client-perspective:
    It sends commands and the other side (the server) has
    to reply with information about its new state or errors.
    Provides (non-)blocking methods to add commands to the
    internal queue, the reply will be printed in a pretty format
    using :func:`locked_print` as soon as it was received.
    Prints error messages if more than 20 unanswered
    commands are pending in the queue or *timeout* is
    reached.
    """
    def __init__(self, socket, timeout=2):
        threading.Thread.__init__(self)
        # we allow at most 20 unhandled srcp-commands at a time
        self.msg_queue = queue.Queue(20)
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
        except queue.Full:
            logger.error("Socket-Fehler: Mehr als 20 unbeantwortete Befehle.")
    
    def send_and_block_for_answer(self, cmd):
        """
        Blocking method which sends *cmd*, waits for the
        answer and then prints out both in a pretty format.
        Returns an error message if timeout was reached.
        """
        try:
            self.socket.send(cmd.encode("ascii"))
        except timeout:
            logger.error("Zeitüberschreitung beim "
                         "Senden des Befehls:\n" + cmd)
        else:
            logger.info("SEND>>: {} RECV<<: {}".format(cmd, self.wait_for_answer()))
    
    def wait_for_answer(self):
        """
        Blocks for a server-reply and
        returns it. Returns an error message if
        timeout was reached.
        """
        try:
            ans = self.socket.recv(4096).decode("ascii")
        except timeout:
            return "Zeitüberschreitung der Server-Antwort."
        else:
            return ans
    
    def run(self):
        while True:
            msg = self.msg_queue.get()
            if msg is None:
                break
            try:
                self.socket.send(msg.encode("ascii"))
            except timeout:
                logger.error("Zeitüberschreitung beim "
                             "Senden des Befehls:\n" + msg)
            else:
                logger.info("SEND>>: {}  RECV<<: {}".format(msg, self.wait_for_answer()))
            self.msg_queue.task_done()
    
    def quit(self):
        self.msg_queue.put(None)
