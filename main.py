# encoding: utf-8
from contextlib import contextmanager
from logging import Logger
import os
import threading
from PySide.QtGui import *
from PySide.QtCore import *
import sys
import time
from libs.logger import LoggerHandler, ColoredFormatter
import maes
from libs.misc import block_size_and_a_byte, block_size, SettingsDialog


class EncPanel(QDialog, object):

    A_MILLION_BYTE = 1024 * 1000

    def __init__(self):
        super(EncPanel, self).__init__()

        self.last_directory = '.'

        self.setup_layout()
        self.setup_logger()
        self.setup_settings_dialog()

        self.connect(self,
                     SIGNAL('accept_drops(bool)'),
                     lambda b: self.setAcceptDrops(b))

        self.setMinimumWidth(400)
        self.setAcceptDrops(True)
        self.setWindowTitle('EncPanel')


    def setup_logger(self):
        self.logger = Logger(__name__)

        color_scheme = ColoredFormatter.gen_colorscheme()

        handler = LoggerHandler(self.text_browser)
        handler.setFormatter(ColoredFormatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M',
            colors={'levelname': lambda lvl: color_scheme[lvl]}
        ))
        self.logger.addHandler(handler)

        self.connect(self.text_browser,
                     SIGNAL('new_log(QString)'),
                     self.text_browser,
                     SLOT('append(QString)'))


    def setup_layout(self):
        self.text_browser = QTextBrowser()
        self.text_browser.setAcceptDrops(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.connect(self.progress,
                     SIGNAL('set_progress(int)'),
                     self.progress,
                     SLOT('setValue(int)'))

        def new_button(name, text, target):
            button = QPushButton(text)
            self.connect(button, SIGNAL('clicked()'), target)
            self.connect(button, SIGNAL('enabled()'),
                         lambda: button.setEnabled(True))
            self.connect(button, SIGNAL('disabled()'),
                         lambda: button.setEnabled(False))
            self.__setattr__(name, button)
            return button

        def new_status_label(name):
            label = QLabel('Not started.')
            label.setAlignment(Qt.AlignCenter)
            self.connect(label, SIGNAL('update(QString)'),
                         label.setText)
            self.__setattr__(name, label)
            return label

        self.file_path_in = QLineEdit()
        in_label = QLabel('&Input Path')
        in_label.setBuddy(self.file_path_in)

        self.file_path_out = QLineEdit()
        out_label = QLabel('Output &Path')
        out_label.setBuddy(self.file_path_out)

        grid = QGridLayout()

        grid.addWidget(self.text_browser, 0, 0, 1, 4)

        grid.addWidget(self.progress, 1, 0, 1, 4)

        grid.addWidget(in_label, 2, 0)
        grid.addWidget(self.file_path_in, 2, 1, 1, 3)
        grid.addWidget(out_label, 3, 0)
        grid.addWidget(self.file_path_out, 3, 1, 1, 3)

        grid.addWidget(new_button('open_button',
                                  '&Open...',
                                  self.select_file), 4, 0)
        grid.addWidget(new_button('enc_button',
                                  '&Enc',
                                  self.start_enc), 4, 1)
        grid.addWidget(new_button('dec_button',
                                  '&Dec',
                                  self.start_dec), 4, 2)
        grid.addWidget(new_button('settings_button',
                                  '&Settings...',
                                  self.show_settings_dialog), 4, 3)

        h = QHBoxLayout()
        h.addWidget(new_status_label('time_elapsed'))
        h.addWidget(new_status_label('processed_size'))
        h.addWidget(new_status_label('instant_speed'))
        grid.addLayout(h, 5, 0, 1, 4)

        self.setLayout(grid)


    def select_file(self, fn=''):
        if not fn:
            fn, _ = QFileDialog.getOpenFileName(self,
                                                'Open File',
                                                self.last_directory)
        if not fn:
            return

        self.last_directory = os.path.dirname(fn)

        self.file_path_in.setText(fn)
        self.file_path_out.setText(fn + '.aes')

        self.logger.info('opened %s', fn)


    def open_files(self):
        in_fn = self.file_path_in.text()
        out_fn = self.file_path_out.text()

        if not in_fn:
            self.select_file()

            in_fn = self.file_path_in.text()
            out_fn = self.file_path_out.text()

            if not in_fn:
                return

        if not out_fn:
            self.logger.error('please specify output path')
            return

        in_fp = open(in_fn, 'rb')
        out_fp = open(out_fn, 'wb')
        self.logger.debug('opened file handler %s', in_fn)
        self.logger.debug('opened file handler %s', out_fn)

        in_fp.seek(0, os.SEEK_END)
        size = in_fp.tell()
        in_fp.seek(0, os.SEEK_SET)

        size_f = float(size)
        if size > 1024 * 1000 * 1000:
            human_readable_size = ' (%.2f GB)' % (size_f /
                                                  (self.A_MILLION_BYTE * 1000))
        elif size > 1024 * 1000:
            human_readable_size = ' (%.2f MB)' % (size_f / self.A_MILLION_BYTE)
        elif size > 1024:
            human_readable_size = ' (%.2f kB)' % (size_f / 1024)
        else:
            human_readable_size = ''
        self.logger.info('source size %s bytes%s',
                         size, human_readable_size)

        return in_fp, out_fp, size


    def setup_settings_dialog(self):
        self.init_vector = '\x00' * 16
        self.key = '\x01\x23\x45\x67\x89\xab\xcd\xef' * 2

        self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.accept()
        self.init_vector, self.key = self.settings_dialog.get_parameters()


    def show_settings_dialog(self):
        ret = self.settings_dialog.exec_()
        if QDialog.Accepted == ret:
            last_iv, last_key = self.init_vector, self.key
            self.init_vector, self.key = self.settings_dialog.get_parameters()

            if last_iv != self.init_vector:
                self.logger.info('initial vector changed')
            if last_key != self.key:
                if len(last_key) != len(self.key):
                    self.logger.info('key length changed to %d',
                                     len(self.key) * 8)
                else:
                    self.logger.info('key changed')


    @staticmethod
    def _cipher_bootstrap(func,
                          key, init_vector,
                          in_fp, out_fp, size,
                          round_callback):
        maes.encrypt('\x00' * 16, key)

        rest_size = size
        processed_size = 0.

        while True:
            if not rest_size:
                break
            elif rest_size > block_size_and_a_byte:
                size = block_size
            else:
                size = rest_size
            out_text, init_vector = func(in_fp.read(size),
                                         init_vector)
            out_fp.write(out_text)
            rest_size -= size
            processed_size += size

            round_callback(processed_size, size)

        return out_fp


    @contextmanager
    def action(self, act, in_fp, out_fp, size):
        act = 'encryption' if act == maes.cbc_aes else 'decryption'

        self.start_time = self.last_time = time.time()

        self.logger.info('beginning %s with %d-bit key',
                         act, len(self.key) * 8)

        yield

        self.enc_button.emit(SIGNAL('enabled()'))
        self.dec_button.emit(SIGNAL('enabled()'))

        self.emit(SIGNAL('accept_drops(bool)'), True)

        in_fp.close()
        out_fp.close()

        time_elapsed = self.last_time - self.start_time
        if time_elapsed > 0:
            t = ('%.2f sec' % time_elapsed) +\
                        ('s' if time_elapsed > 1 else '')
            avg_speed = '%.2f MB/s' %\
                            (float(size) / time_elapsed / self.A_MILLION_BYTE)
        else:
            t = '0.00 sec'
            avg_speed = 'inf'
        self.logger.info('%s done within %s, average speed %s',
                         act, t, avg_speed)


    def start_action(self, action, file_state, round_callback):
        def _(in_fp, out_fp, size):
            with self.action(action, in_fp, out_fp, size):
                self._cipher_bootstrap(action,
                                       self.key, self.init_vector,
                                       in_fp, out_fp, size,
                                       round_callback)

        thread = threading.Thread(target=_, args=file_state)
        thread.start()


    def dragEnterEvent(self, event):
        event.accept()


    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        file_url = event.mimeData().urls()[0]
        self.select_file(file_url.toLocalFile())


    def gen_callback(self, total):
        def callback(processed_size, block_size):
            this_time = time.time()
            time_elapsed = this_time - self.last_time
            self.last_time = this_time

            total_elapsed = self.last_time - self.start_time

            self.time_elapsed.emit(SIGNAL('update(QString)'),
                                   time.strftime('%H:%M:%S',
                                                 time.gmtime(total_elapsed)))

            if time_elapsed > 0:
                speed = float(block_size) / time_elapsed / self.A_MILLION_BYTE
                self.instant_speed.emit(SIGNAL('update(QString)'),
                                        '%.2f MB/s' % speed)
            else:
                self.instant_speed.emit(SIGNAL('update(QString)'),
                                        'inf MB/s')

            processed_MB = processed_size / self.A_MILLION_BYTE
            self.processed_size.emit(SIGNAL('update(QString)'),
                                     '%.2f MB' % processed_MB)

            self.progress.emit(SIGNAL('set_progress(int)'),
                               int(processed_size / total * 100))

        return callback


    def initialize_action(self):
        self.enc_button.setEnabled(False)
        self.dec_button.setEnabled(False)
        self.setAcceptDrops(False)

        self.progress.reset()
        self.time_elapsed.setText('')
        self.instant_speed.setText('0 MB/s')
        self.processed_size.setText('0 MB')


    def start_enc(self):
        fp = _, _, total = self.open_files()

        self.initialize_action()
        self.start_action(maes.cbc_aes,
                          fp,
                          self.gen_callback(total))


    def start_dec(self):
        fp = _, _, total = self.open_files()

        self.initialize_action()
        self.start_action(maes.inv_cbc_aes,
                          fp,
                          self.gen_callback(total))



if __name__ == '__main__':
    app = QApplication(sys.argv)
    panel = EncPanel()
    panel.show()

    app.exec_()



