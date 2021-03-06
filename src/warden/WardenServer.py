import sys
import os
import signal
import time
import ConfigParser
import logging
from CarbonManager import CarbonManager
from GentryManager import GentryManager
from DiamondManager import DiamondManager
from SMTPForwarderManager import SMTPForwarderManager
from warden import AutoConf
from warden_logging import log
from warden_utils import StartupException, relative_to_config_file
import datetime



class WardenServer(object):
    """
    Warden is a solution for controlling Carbon daemons, Sentry, Graphite-web and Diamond all within a single process.
    The sub systems all run in separate threads and can be shutdown gracefully using sigint or stop commands.
    """
    
    def __init__(self, home):
        """
        Load configuration object
        """
        AutoConf.autoconf(home)
        self.configuration = AutoConf.get_warden_conf()

        # Setup logger
        # this is the stdout log level
        loglevel = getattr(logging, self.configuration.get('warden', {}).get('loglevel', 'INFO'))
        log.setLevel(loglevel)

        self.startuptime = None
        self.shutdowntime = None
        self.smtp_forwarder_enabled = str(self.configuration.get('smtp_forwarder', {}).get('enabled', '')).lower() in ('true', 't', '1', 'yes', 'y')

        log.info('Initialising Warden..')
        try:
            # initialise Carbon, daemon services are setup here, but the event reactor is not yet run
            self.carbon = CarbonManager()

            # initialise Gentry, this will also perform database manipulation for Sentry
            self.gentry = GentryManager()

            # initialise Diamond, not much is required here
            self.diamond = DiamondManager()


            if self.smtp_forwarder_enabled:
                self.smtpforward = SMTPForwarderManager(dict(self.configuration.get('smtp_forwarder', {})))

        except Exception:
            log.exception("An error occured during initialisation.")
            sys.exit(1)

    def _startup(self):
        """
        Start the warden instance
        Carbon, Diamond and Gentry are started in order, and this method will only exit once all are bound to their
        correct ports
        """

        log.info('Starting Warden..')
        try:
            self.carbon.start()
            self._wait_for_start(self.carbon)
            log.info('1. Carbon Started')

            self.diamond.start()
            self._wait_for_start(self.diamond)
            log.info('2. Diamond Started')

            self.gentry.start()
            self._wait_for_start(self.gentry)
            log.info('3. Gentry Started')

            if self.smtp_forwarder_enabled:
                self.smtpforward.start()
                log.info('4. Graphite SMTP forwarder Started')

            # blocking
            log.info('Started Warden.')
            self.startuptime = self.shutdowntime = datetime.datetime.now()

        except Exception, e:
            raise StartupException(e)

    def _wait_for_start(self, process):
        while not process.is_active():
            time.sleep(0.5)

    def _is_active(self):
        """
        A general active state query.
        returns False as soon as anything is not running
        """
        return self.gentry.is_active() and self.carbon.is_active() and self.diamond.is_active()

    def _shutdown(self):
        """
        Shutdown in order, some threading may be wrong here, make sure of inidividual .join()
        """
        self.shutdowntime = datetime.datetime.now()

        elapsed = self.shutdowntime - self.startuptime
        log.info('Warden was active for %s' % str(elapsed))

        log.info('Shutting down Warden..')

        if self.smtp_forwarder_enabled:
            try:
                self.smtpforward.stop()
                log.info('4. Graphite SMTP forwarder stopped')
            except Exception:
                log.exception('An error occured while shutting down Graphite SMTP forwarder')

        try:
            self.gentry.stop()
            log.info('3. Gentry Stopped.')
        except Exception:
            log.exception("An error occured while shutting down Gentry")

        try:
            self.diamond.stop()
            log.info('2. Diamond Stopped.')
        except Exception:
            log.exception("An error occured while shutting down Diamond")

        try:
            self.carbon.stop()
            log.info('1. Carbon Stopped.')
        except Exception:
            log.exception("An error occured while shutting down Carbon")

        log.info('Shut down Warden.')

    def start(self):
        try:
            self._startup()
            while True:
                time.sleep(5)
                if not self._is_active():
                    log.error("Something caused one of the services to stop!")
                    break
                # need some way to pickup errors at runtime. should check after each sleep whether any of the
                # services have picked up an error

        except KeyboardInterrupt:
            log.info("Keyboard interrupt received.")
            self._shutdown()
        except StartupException:
            log.exception("An error occured during startup.")
            self._shutdown()
        except Exception:
            log.exception("An error occured while running.")
            self._shutdown()

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Warden Server')
    parser.add_argument('home', nargs='?', help="the warden home folder")
    parser.add_argument('--pid-file', help="PID file for Daemon mode.  This causes Warden to run in Daemon mode", dest='pid_file')
    parser.add_argument('--stop', help='Stop Warden running in Daemon mode', action='store_true', default=False)
    args = parser.parse_args()
    if args.stop and not args.pid_file:
        log.error('Warden cannot stop daemon mode unless the pid-file is specified')
        sys.exit(1)
    if args.stop:
        pid_file = os.path.abspath(os.path.expanduser(args.pid_file))
        if not os.path.exists(pid_file):
            log.error('Warden cannot find pid-file %s',pid_file)
            sys.exit(1)
        pid = int(open(pid_file, 'r').readline())
        log.info('Killing pid %d', pid)
        os.kill(pid, signal.SIGINT)
        # Check if we've managed for 10 seconds
        for i in range(10):
            try:
                os.kill(pid, 0)
                log.info('Waiting for %d to die', pid)
            except OSError:
                log.info('Stop complete')
                return
            time.sleep(1)
        log.warning("Could not end warden process - killing manually")
        os.kill(pid, signal.SIGHUP)
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return
    home = AutoConf.get_home(args.home)
    if not os.path.exists(home):
        log.error('The warden home specified ("%s") does not exist!' % home)
        sys.exit(1)

    if args.pid_file:
        pid_file = os.path.abspath(os.path.expanduser(args.pid_file))
        import daemon
        from lockfile import pidlockfile
        context = daemon.DaemonContext(pidfile=pidlockfile.PIDLockFile(pid_file))
        with context:
            warden_server = WardenServer(home)
            warden_server.start()
        return
    warden_server = WardenServer(home)
    warden_server.start()

if __name__ == '__main__':
    main()
