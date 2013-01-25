import threading
import re
import os
import smtplib
import time
from smtplib import SMTP
from smtp_forwarder import BaseMailGenerator
from warden_logging import log
from  smtp_forwarder import GraphiteMailGenerator
from configobj import ConfigObj


class SMTPForwarderManager:

    def __init__(self, config_file):

        config_file = os.path.expandvars(os.path.expanduser(config_file))

        self.dispatcherThread = self.CentralDispatcherThread(config_file)

    def start(self):
        log.debug('Starting Graphite SMTP forwader...')
        self.dispatcherThread.start()
        log.debug('Started Graphite SMTP forwader.')

    def stop(self):
        log.debug('Stopping Graphite SMTP forwader...')
        self.dispatcherThread.stop()
        log.debug('Stopped Graphite SMTP forwader.')

    class CentralDispatcherThread(threading.Thread):

        def __init__(self, config_file):
            threading.Thread.__init__(self)
            self.running = False
            self.config_file = config_file

        def compile_metric_patterns(self, old_patterns):

            compiled = []
            for p in old_patterns:
                if p.endswith('.wsp'):
                    p = p[:-4]
                p = p.replace('.', os.path.sep).replace('\\','\\\\').replace('*','.+')
                p = ".*%s\\.wsp$" % p
                compiled.append(re.compile(p))

            return compiled

        def run(self):
            self.running = True

            self.configuration = ConfigObj(self.config_file)
            self.configuration['METRIC_PATTERNS_TO_SEND'] = self.compile_metric_patterns(self.configuration['METRIC_PATTERNS_TO_SEND'])

            self.SLEEP_TIME = int(self.configuration['SEND_INTERVAL'])
            self.last_poll_time = time.time()

            while self.running:
                if (time.time()-self.last_poll_time) < self.SLEEP_TIME:
                    time.sleep(1)
                    continue

                self.configuration = ConfigObj(self.config_file)
                self.configuration['METRIC_PATTERNS_TO_SEND'] = self.compile_metric_patterns(self.configuration['METRIC_PATTERNS_TO_SEND'])

                conn = SMTP()
                try:
                    log.debug('Connecting...')
                    conn.connect(self.configuration['EMAIL_HOST'])
                    conn.set_debuglevel(False)

                    if self.configuration['EMAIL_USE_TLS']:
                        conn.starttls()

                    log.debug('Logging in..')
                    conn.login(self.configuration['EMAIL_USERNAME'], self.configuration['EMAIL_PASSWORD'])
                    max_mail_size = int(conn.esmtp_features['size'])

                    for generator_cls in BaseMailGenerator.generator_registry:
                        generator = generator_cls(self.configuration, max_mail_size)
                        mails = generator.get_mail_list()

                        for mail in mails:
                            if mail:

                                bytes = len(mail.as_string())
                                if bytes < 1024:
                                    sizestr = str(bytes) + "b"
                                elif bytes < 1048576:
                                    sizestr = "%.2f Kb" % (bytes/1024.0)
                                else:
                                    sizestr = "%.2f Mb" % ((bytes/1024.0)/1024.0)

                                log.debug('%s: Sending mail to: %s Size: %s' % (generator.__class__.__name__, mail['To'],sizestr))

                                start_time = time.time()
                                conn.sendmail(mail['From'], mail['To'], mail.as_string())
                                log.debug('Sent mail in %d seconds.' % (time.time()-start_time))

                    self.last_poll_time = time.time()
                except smtplib.SMTPRecipientsRefused:
                    log.error('STMPRecipientsRefused')
                except smtplib.SMTPHeloError:
                    log.error('SMTPHeloError')
                except smtplib.SMTPSenderRefused:
                    log.exception('SMTPSenderRefused')
                except smtplib.SMTPDataError:
                    log.error('SMTPDataError')
                except Exception as exc:
                    log.exception('An exception occured when sending mail')
                finally:
                    # Did it fail to send
                    if time.time() - self.last_poll_time > self.SLEEP_TIME:
                        self.last_poll_time = time.time() + (60 * 10) - self.SLEEP_TIME

                    if hasattr(conn, 'sock') and conn.sock:
                        conn.quit()

        def stop(self):
            self.running = False