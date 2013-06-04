# encoding: utf-8
import hashlib
import struct
from PySide.QtGui import *
from PySide.QtCore import *
import sys


CHUNK_SIZE = 8192 * 128
CHUNK_SIZE_AND_A_BLOCK = CHUNK_SIZE + 16


class SettingsDialog(QDialog, object):
    """Settings dialog for EncPanel.
    Use `get_parameter` to get key and initial vector."""

    def __init__(self, parent):
        super(SettingsDialog, self).__init__(parent)
        self.parent = parent

        self.setup_layout()


    def setup_layout(self):
        class PasswordKeySettingWidget(QWidget, object):
            def __init__(self, parent):
                super(PasswordKeySettingWidget, self).__init__(parent=parent)

                label = QLabel('&Password')
                self.password_widget = QLineEdit('123456')
                label.setBuddy(self.password_widget)

                self.message_widget = QLabel()
                self.message_widget.setAlignment(Qt.AlignRight)

                layout = QGridLayout()
                layout.addWidget(label, 0, 0)
                layout.addWidget(self.password_widget, 0, 1)
                layout.addWidget(self.message_widget, 0, 2)

                group_box = QGroupBox('Use password as key')
                group_box.setLayout(layout)

                _l = QVBoxLayout()
                _l.addWidget(group_box)
                self.setLayout(_l)

                self.connect(self.password_widget,
                             SIGNAL('textChanged(QString)'),
                             self.update_message_widget)
                self.password_widget.emit(SIGNAL('textChanged(QString)'),
                                          '123456')

            def update_message_widget(self, s):
                if len(s) > 10:
                    self.message_widget.setText('<font color=green>'
                                                    'Strong'
                                                '</font>')
                elif len(s) > 5:
                    self.message_widget.setText('<font color=orange>'
                                                    'Acceptable'
                                                '</font>')
                else:
                    self.message_widget.setText('<font color=red>'
                                                    'Weak'
                                                '</font>')

        class FileKeySettingWidget(QWidget, object):
            def __init__(self, parent):
                super(FileKeySettingWidget, self).__init__(parent)
                self.parent = parent

                label = QLabel('P&ath')
                self.path_widget = QLineEdit()
                label.setBuddy(self.path_widget)

                open_button = QPushButton('&Open...')

                layout = QGridLayout()
                layout.addWidget(label, 0, 0)
                layout.addWidget(self.path_widget, 0, 1)
                layout.addWidget(open_button, 0, 3)

                group_box = QGroupBox('Use file as key')
                group_box.setLayout(layout)

                _l = QVBoxLayout()
                _l.addWidget(group_box)
                self.setLayout(_l)

                self.connect(open_button, SIGNAL('clicked()'),
                             self.open_file)

            def open_file(self):
                fn, _ = QFileDialog.getOpenFileName(
                    self,
                    self.parent.parent.last_directory,
                    'Open key file'
                )
                self.path_widget.setText(fn)

        def make_radio_button(name, text):
            radio_button = QRadioButton(text)
            self.__setattr__(name, radio_button)
            return radio_button

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(make_radio_button('password_key_radio_btn',
                                                    'Use password as key'), 1)
        self.mode_group.addButton(make_radio_button('file_key_radio_btn',
                                                    'Use file as key'), 2)

        radio_label = QLabel('Key length')
        self.key_len_group = QButtonGroup(self)
        self.key_len_group.addButton(make_radio_button('radio_btn_128',
                                                       '128-bit'), 1)
        self.key_len_group.addButton(make_radio_button('radio_btn_192',
                                                       '192-bit'), 2)
        self.key_len_group.addButton(make_radio_button('radio_btn_256',
                                                       '256-bit'), 3)

        stacked_widget = QStackedWidget()
        self.password_key_page = PasswordKeySettingWidget(self)
        self.file_key_page = FileKeySettingWidget(self)
        stacked_widget.addWidget(self.password_key_page)
        stacked_widget.addWidget(self.file_key_page)

        label = QLabel('IV')
        self.init_vector_widget = QLineEdit('00' * 16)
        label.setBuddy(self.init_vector_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok |
                                      QDialogButtonBox.Cancel)

        layout = QVBoxLayout()

        _l = QHBoxLayout()
        _l.addWidget(self.password_key_radio_btn)
        _l.addWidget(self.file_key_radio_btn)
        layout.addLayout(_l)

        layout.addWidget(stacked_widget)

        _l = QGridLayout()
        _l.addWidget(radio_label, 0, 0)
        _l.addWidget(self.radio_btn_128, 0, 1)
        _l.addWidget(self.radio_btn_192, 0, 2)
        _l.addWidget(self.radio_btn_256, 0, 3)
        _l.addWidget(label, 1, 0)
        _l.addWidget(self.init_vector_widget, 1, 1, 1, 3)
        layout.addLayout(_l)

        layout.addWidget(button_box)

        self.setLayout(layout)

        self.connect(self.password_key_radio_btn, SIGNAL('toggled(bool)'),
                     lambda b: stacked_widget.setCurrentIndex(0))
        self.connect(self.file_key_radio_btn, SIGNAL('toggled(bool)'),
                     lambda b: stacked_widget.setCurrentIndex(1))
        self.connect(button_box, SIGNAL('accepted()'),
                     self, SLOT('accept()'))
        self.connect(button_box, SIGNAL('rejected()'),
                     self, SLOT('reject()'))

        self.radio_btn_128.setChecked(True)
        self.password_key_radio_btn.setChecked(True)

        self.setModal(True)

        self.setWindowTitle('Settings')


    def accept(self):
        iv = self.init_vector_widget.text()
        if len(iv) != 32:
            QMessageBox.critical(self,
                                 'Error', 'Invalid initial vector.',
                                 QMessageBox.Ok)
            return
        else:
            # convert '00000000' to '\x00\x00\x00\x00'
            self.init_vector = ''.join([struct.pack('B',
                                                    int(iv[i:i + 2],
                                                        base=16))
                                        for i in range(0, len(iv), 2)])
            assert len(self.init_vector) == 16

        to_digest = None
        checked_id = self.mode_group.checkedId()
        if checked_id == 1:
            pwd = self.password_key_page.password_widget.text()
            if len(pwd) < 6:
                ret = QMessageBox.warning(self,
                                          'Warning', 'Weak password. Proceed?',
                                          QMessageBox.Yes | QMessageBox.No)
                if ret == QMessageBox.No:
                    return
            to_digest = pwd
        if checked_id == 2:
            path = self.file_key_page.path_widget.text()
            if not path:
                QMessageBox.critical(self,
                                     'Error', 'Invalid key file.',
                                     QMessageBox.Ok)
                return
            with open(path, 'rb') as f:
                to_digest = f.read()
            if not to_digest:
                QMessageBox.critical(self,
                                     'Error', 'Invalid key file.',
                                     QMessageBox.Ok)
                return

        if not to_digest:
            return

        # use sha256 to generate 256-bit digest
        # and truncate it to the size wanted
        self.key = hashlib.sha256(to_digest).digest()[:
                {1: 16,
                 2: 24,
                 3: 32}[self.key_len_group.checkedId()]
        ]

        return super(SettingsDialog, self).accept()


    def get_parameters(self):
        return self.init_vector, self.key



class TaskBuffer(QObject, object):
    """Object which buffers tasks for asynchronized task support.
    Inherits QObject so that signals and slots can be implemented.

    signals:
    extend_buffer(list): emitted when new tasks are added
    task_finished(str): emitted when self.buffer is empty

    slots:
    extend(l: list): extend buffer
    new_task(act: str): activate new task from self.buffer, whether it is an
                        encrypting task or decrypting task is
                        depended on `act`"""

    extend_buffer = Signal(list)
    task_finished = Signal(str)

    def __init__(self, target, logger):
        super(TaskBuffer, self).__init__()

        self.buffer = []
        self.target = target
        self.logger = logger

        self.extend_buffer.connect(self.extend)
        self.task_finished.connect(self.new_task)


    @Slot(list)
    def extend(self, l):
        for item in l:
            self.buffer.append(item)
            self.logger.info('added %s to buffer', item)
        self.refresh_buffer_label()


    @Slot(str)
    def new_task(self, act):
        if self.buffer:
            self.target.start_task.emit(act, self.buffer.pop(0))
        else:
            self.target.all_task_done.emit()
        self.refresh_buffer_label()


    def refresh_buffer_label(self):
        self.target.buffer_rest.emit(SIGNAL('update(QString)'),
                                     'buffer: %s' % len(self.buffer))




if __name__ == '__main__':
    app = QApplication(sys.argv)

    dialog = SettingsDialog(None)
    dialog.show()

    app.exec_()


