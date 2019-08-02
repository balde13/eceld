#!/usr/bin/env python
# saved as greeting-server.py
import Pyro4
from engine.engine import Engine
import logging
import os

@Pyro4.expose
class ECELDaemon(object):
    def __init__(self, *args, **kwargs):
        logging.debug("Initializing ECELDaemon()")
        #get the engine object
        self.engine = Engine()
        logging.debug("Completed initializing ECELDaemon()")

    def start_collectors(self):
        logging.debug("Instantiating start_collectors()")
        collectors = self.engine.get_all_collectors()
        for i, collector in enumerate(collectors):
            if collector.name != 'manualscreenshot':
                logging.info("Starting Collector: " + collector.name)
                self.engine.start_collector(collector)
        logging.debug("Completed start_collectors()")
        return "Collectors started"

    def stop_collectors(self):
        logging.debug("Instantiating stop_collectors()")
        collectors = self.engine.get_all_collectors()
        for i, collector in enumerate(collectors):
            if collector.name != 'manualscreenshot':
                logging.info("Starting Collector: " + collector.name)
                self.engine.start_collector(collector)

        logging.debug("Completed stop_collectors()")
        return "Collectors stopped"

    def export_data(self, path=None):
        logging.debug("Instantiating export_data()")
        if path == None or os.path.exists(path) == False:
            logging.warning("Valid path was not provided: " + str(path) + ". Writing to /tmp/")
            path = "/tmp/"
        logging.debug("Exporting data to: " + str(path))
        self.engine.export(path)
        logging.debug("Completed export_data()")

    def remove_data(self):
        logging.debug("Instantiating remove_data()")
        self.engine.delete_all()
        logging.debug("Completed remove_data()")

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    daemon = Pyro4.Daemon()                # make a Pyro daemon
    ns = Pyro4.locateNS()                  # find the name server
    uri = daemon.register(ECELDaemon)   # register the greeting maker as a Pyro object
    ns.register("ecel.service", uri)   # register the object with a name in the name server

    logging.info("ECELd Engine Started")
    daemon.requestLoop()                   # start the event loop of the server to wait for calls
