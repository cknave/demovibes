import socket
import logging
import threading

Log = logging

class messenger(threading.Thread):
    def __init__(self, sock, events, eventid):
        threading.Thread.__init__(self)
        self.sock = sock
        self.eventid = eventid
        self.events = events

    def mk_message(self, id, user = ""):
        events = []
        Log.debug("Message construct: id = '%s' and user = '%s'" % (id, user))
        for e in self.events:
            Log.debug("Message: checking event (user %s, id %s) : %s" % (e['user'], e['id'], e['event']) )
            if int(e['id']) > int(id) and (e['user'] == user or e['user'] == ""):
                if not e['event'] in events:
                    events.append(e['event'])
        message = "\n".join(events) + "\n!%s" % self.eventid
        Log.debug("Make message: %s" % message)
        return message

    def send_message(self, sock):
        Log.debug("Sending message to socket")
        message = self.mk_message(sock['id'], sock['user'])
        ml = len(message)
        sent = 0
        while ml > sent:
            sent += sock['conn'].send(message[sent:ml])
        sock['conn'].close()

    def run(self):
        self.send_message(self.sock)

class locoland:
    def __init__(self, host = "127.0.0.1", port = 9911, max_events = 20):
        self.events = []
        self.eventid = 0
        self.waiters = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((host, port))
        Log.info("Set up for host %s and port %s" % (host, port))
        self.max_events = max_events
        self.on = True

    def add_event(self, event, user = ""):
        Log.debug("New event : %s" % event)
        self.eventid += 1
        if not event in self.events: # always true ATM...
            self.events.insert(0, {'id': self.eventid, 'event': event, 'user': user})
            self.events = self.events[0:self.max_events]
            self.send_events()

    def send_events(self):
        Log.debug("Sending events to %s clients" % len(self.waiters))
        events = self.events[:]
        threads = []
        eventid = int(self.eventid)
        while self.waiters:
            sock = self.waiters.pop()
            t = messenger(sock, events, eventid)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def send_message(self, info):
        th = messenger(info, self.events, self.eventid)
        th.start()

    def listen(self):
        while self.on:
            Log.debug("Listening for new connection")
            self.sock.listen(1)
            conn, addr = self.sock.accept()
            try:
                recv = conn.recv(1024)
                key, user, data = recv.strip().split(":", 2)
                Log.debug("Got a new connection with key '%s', user '%s' and data '%s'"% (key, user, data))
                if key == "get":
                    info = {'conn' : conn, 'user': user, 'id': data}
                    if int(data) < self.eventid:
                        self.send_message(info)
                    else:
                        self.waiters.append(info)
                        Log.debug("Adding connecton to waiter list (%s in list)" % len(self.waiters))
                
                if key == "set":
                    self.add_event(data, user)
                    conn.send("OK")
                    conn.close()
            
                if key == "die":
                    Log.debug("Dying")
                    conn.send("BYE")
                    conn.close()
                    self.on = False
                    
                if key == "event":
                    conn.send("%s\n" % self.eventid)
                    conn.close()
            except 99999:
                conn.send("ERROR")
                Log.warn("Error occurred, data : %s" % recv)
                conn.close()

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port", default="9911", help = "Which port to listen to")
    parser.add_option("-i", "--ip", dest="ip", default="127.0.0.1", help="What IP address to bind to")
    parser.add_option("-e", "--events", dest="events", default="20", help="Max events to hold")
    (options, args) = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    
    HOST = options.ip
    PORT = int(options.port)
    EVENTS = int(options.events)
    moo = locoland(host = HOST, port = PORT, max_events = EVENTS)
    moo.listen()
