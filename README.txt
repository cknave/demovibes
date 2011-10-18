What Is This?
=============

This is an engine for streaming music, similar to the Nectarine demoscene radio. It allows the users to queue up songs which are then played in the order they are queued.

What you need
=============

# Linux. At present the setup has been tested on Ubuntu 8.1 - 9.10 and Debian 5.
# Python 2.4 and above
# Django 1.0+, South 0.5+, Flup
# A Database + python bindings.
 * I'd recommend sqlite for testing, but MySQL and Postgresql are also supported. 
# For streaming ices0 need to be compiled with Python module support. For re-encoding support, LAME and applicable libraries must also be present (see setup-debian.sh).

Installation
============

See contrib/INSTALL

Streaming
=========

   1. Create user djrandom that the script will use for random songs
   2. Start the streamer with the icecaster.sh script 

Contact / updates
=================

Latest version is avaliable at http://code.google.com/p/demovibes
Authors can be contacted at terra@thelazy.net (Terrasque) and andy@f1-software.com (FishGuy876)


This code is released as GPL. May contain traces of NUTS!
