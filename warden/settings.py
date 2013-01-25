import logging

# WARDEN GENERAL
# ----------------

STDOUT_LEVEL = logging.DEBUG

# DIAMOND
# ----------------
# path to diamond.conf
DIAMOND_CONFIG = '~/.diamond/etc/diamond/diamond.conf'
# logging level of diamond. this produces a lot of logs if set to info/debug
DIAMOND_STDOUT_LEVEL = logging.ERROR
# path to diamond_root
DIAMOND_ROOT = None

# GENTRY
# ----------------
# path to the gentry settings.py file
GENTRY_SETTINGS_PATH = None
# optional path to an overriding sentry secret key
SENTRY_KEY_FILE = None

# CARBON
# ----------------
# path to graphite root
GRAPHITE_ROOT = '~/.graphite'

# the path to the carbon config is derived from the GRAPHITE_ROOT unless defined here
CARBON_CONFIG = '~/.graphite/conf/carbon.conf'

# SMTP FORWARDER
# ---------------

START_SMTP_FORWARDER = False
SMTP_FORWARDER_CONFIG = None


