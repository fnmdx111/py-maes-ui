# encoding: utf-8

import sys


gui = True
try:
    from PySide.QtCore import *
    from PySide.QtGui import *
except ImportError:
    # qt not loaded, unable to run in graphics mode
    gui = False


maes_found = True
try:
    import libs.maes
except ImportError:
    # maes not loaded, consider recompile it
    maes_found = False

if not maes_found:
    if not gui:
        print 'cannot load MAES, make sure you have run' \
              '\n\tpython setup.py install\nor put it into `./libs/\''
    else:
        app = QApplication(sys.argv)
        QMessageBox.critical(None,
                             'Error',
                             'Cannot load MAES,\n'
                             'make sure you have run\n'
                             '        python setup.py install\n'
                             'or put it into `./libs/\'',
                             QMessageBox.Ok)
if not gui:
    print 'cannot load PySide, thus the program cannot be loaded'
else:
    from main import EncPanel

    app = QApplication(sys.argv)

    panel = EncPanel()
    panel.show()

    app.exec_()


