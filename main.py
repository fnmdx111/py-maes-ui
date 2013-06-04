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
from libs.misc import CHUNK_SIZE_AND_A_BLOCK, CHUNK_SIZE, SettingsDialog, TaskBuffer


class EncPanel(QDialog, object):
    """GUI part of MAES.

    signals:
    accept_drops(bool): emitted when panel changes drop policy
    start_task(str, str): emitted when new task is to start
    all_task_done(): emitted task buffer is empty
    other widget signals are omitted

    slots:
    finalize_task_buffer(): reset panel state to initial state
    start_new_task(act: str, fn: str): start new task,
                                       args are action type and file path"""

    A_MILLION_BYTE = 1024 * 1000

    ACT_ENC = 'encryption'
    ACT_DEC = 'decryption'

    accept_drops = Signal(bool)
    start_task = Signal(str, str)
    all_task_done = Signal()

    def __init__(self):
        super(EncPanel, self).__init__()

        self.last_directory = '.'

        self.setup_layout()
        self.setup_logger()
        self.setup_settings_dialog()

        self.accept_drops.connect(lambda b: self.setAcceptDrops(b))
        self.start_task.connect(self.start_new_task)
        self.all_task_done.connect(self.finalize_task_buffer)

        self.task_buffer = TaskBuffer(self, self.logger)

        self.task_buffer.refresh_buffer_label()

        self.reset_idleness()

        self.setMinimumWidth(400)
        self.setAcceptDrops(True)
        self.setWindowTitle('EncPanel')


    @Slot()
    def finalize_task_buffer(self):
        self.enc_button.emit(SIGNAL('enabled()'))
        self.dec_button.emit(SIGNAL('enabled()'))

        self.reset_idleness()


    @Slot(str, str)
    def start_new_task(self, act, fn):
        self.echo_selected_file(fn, '%s.aes' % fn)

        if act == self.ACT_ENC:
            self.start_enc()
        elif act == self.ACT_DEC:
            self.start_dec()


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
        self.connect(self.file_path_in, SIGNAL('clear(QString)'),
                     self.file_path_in.setText)

        self.file_path_out = QLineEdit()
        out_label = QLabel('Output &Path')
        out_label.setBuddy(self.file_path_out)
        self.connect(self.file_path_out, SIGNAL('clear(QString)'),
                     self.file_path_out.setText)

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
        h.addWidget(new_status_label('idleness'))
        h.addWidget(new_status_label('time_elapsed'))
        h.addWidget(new_status_label('processed_size'))
        h.addWidget(new_status_label('instant_speed'))
        h.addWidget(new_status_label('buffer_rest'))
        grid.addLayout(h, 5, 0, 1, 4)

        self.setLayout(grid)


    def select_file(self, fn=''):
        if not fn:
            fns, _ = QFileDialog.getOpenFileNames(self,
                                                  'Open File',
                                                  self.last_directory)
        else:
            fns = [fn]

        if not fns:
            return

        fn = fns[0]

        self.last_directory = os.path.dirname(fn)

        self.echo_selected_file(fn, '%s.aes' % fn)

        self.emit_extend_buffer(fns[1:])


    def echo_selected_file(self, in_fn, out_fn):
        self.file_path_in.setText(in_fn)
        self.file_path_out.setText(out_fn)
        self.logger.info('selected %s', in_fn)


    def open_files(self):
        in_fn = self.file_path_in.text()
        out_fn = self.file_path_out.text()

        ret_failed = None, None, 0
        if not in_fn:
            self.select_file()

            in_fn = self.file_path_in.text()
            out_fn = self.file_path_out.text()

            if not in_fn:
                return ret_failed

        if not out_fn:
            self.logger.error('please specify output path')
            return ret_failed

        in_fp = open(in_fn, 'rb')
        out_fp = open(out_fn, 'wb')
        self.logger.debug('opened file handler %s', in_fn)
        self.logger.debug('opened file handler %s', out_fn)

        in_fp.seek(0, os.SEEK_END)
        size = in_fp.tell()
        in_fp.seek(0, os.SEEK_SET)

        self.logger.info('source size %s (%s bytes)',
                         self.to_human_readable(size), size)

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
            elif rest_size > CHUNK_SIZE_AND_A_BLOCK:
                size = CHUNK_SIZE
            else:
                size = rest_size
            out_text, init_vector = func(in_fp.read(size),
                                         init_vector)
            out_fp.write(out_text)
            rest_size -= size
            processed_size += size

            round_callback(processed_size, size)

        return out_fp


    def to_human_readable(self, size):
        size_f = float(size)
        if size > 1024 * 1000 * 1000:
            human_readable_size = '%.2f GB' % (size_f /
                                                  (self.A_MILLION_BYTE * 1000))
        elif size > 1024 * 1000:
            human_readable_size = '%.2f MB' % (size_f / self.A_MILLION_BYTE)
        elif size > 1024:
            human_readable_size = '%.2f kB' % (size_f / 1024)
        else:
            human_readable_size = '%.2f B' % size_f
        return human_readable_size


    @contextmanager
    def action(self, act, in_fp, out_fp, size):
        act = self.ACT_ENC if act == maes.cbc_aes else self.ACT_DEC

        self.start_time = self.last_time = time.time()

        self.logger.info('beginning %s with %d-bit key',
                         act, len(self.key) * 8)

        yield

        in_fp.close()
        out_fp.close()

        time_elapsed = self.last_time - self.start_time
        if time_elapsed > 0:
            t = ('%.2f sec' % time_elapsed) +\
                        ('s' if time_elapsed > 1 else '')
            avg_speed = '%s/s' %\
                            self.to_human_readable(float(size) / time_elapsed)
        else:
            t = '0.00 sec'
            avg_speed = 'inf'

        self.file_path_in.emit(SIGNAL('clear(QString)'), '')
        self.file_path_out.emit(SIGNAL('clear(QString)'), '')

        self.logger.info('%s done within %s, average speed %s',
                         act, t, avg_speed)
        self.task_buffer.task_finished.emit(act)


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

        fns = [item.toLocalFile() for item in event.mimeData().urls()]

        self.emit_extend_buffer(fns)


    def emit_extend_buffer(self, fns):
        if not self.file_path_in.text():
            pending = fns[1:]
            self.select_file(fns[0])
        else:
            pending = fns

        self.task_buffer.extend_buffer.emit(pending)


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
                speed = float(block_size) / time_elapsed
                self.instant_speed.emit(SIGNAL('update(QString)'),
                                        '%s/s' % self.to_human_readable(speed))
            else:
                self.instant_speed.emit(SIGNAL('update(QString)'),
                                        'inf')

            self.processed_size.emit(SIGNAL('update(QString)'),
                                     self.to_human_readable(processed_size))

            self.progress.emit(SIGNAL('set_progress(int)'),
                               int(processed_size / total * 100))

        return callback


    def reset_idleness(self):
        self.idleness.setText('<font color=orange><b>idle</b></font>')


    def initialize_action(self):
        self.enc_button.setEnabled(False)
        self.dec_button.setEnabled(False)

        self.progress.reset()
        self.time_elapsed.setText('')
        self.instant_speed.setText('0 MB/s')
        self.processed_size.setText('0 MB')


    def start_enc(self):
        fp = _, _, total = self.open_files()

        if None in fp:
            return

        self.initialize_action()
        self.idleness.setText('<font color=green><b>enc</b></font>')
        self.start_action(maes.cbc_aes,
                          fp,
                          self.gen_callback(total))


    def start_dec(self):
        fp = _, _, total = self.open_files()

        if None in fp:
            return

        self.initialize_action()
        self.idleness.setText('<font color=green><b>dec</b></font>')
        self.start_action(maes.inv_cbc_aes,
                          fp,
                          self.gen_callback(total))



if __name__ == '__main__':
    app = QApplication(sys.argv)

    panel = EncPanel()
    panel.show()

    app.exec_()



