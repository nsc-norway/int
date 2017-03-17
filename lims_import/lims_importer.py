import sys
import requests
from genologics.lims import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication, pyqtSignal


lims = None

class LoginBox(QDialog):

    finishLogin = pyqtSignal()

    def __init__(self, parent, lims_url):
        super().__init__(parent)
        self.resize(300, 70)
        self.setModal(True)
        self.setWindowTitle("Log in to LIMS...")
        
        grid = QGridLayout()

        grid.addWidget(QLabel("User:"), 0, 0)
        self.text_user = QLineEdit(self)
        self.text_user.textChanged.connect(self.changed)
        grid.addWidget(self.text_user, 0, 1)

        grid.addWidget(QLabel("Password:"), 1, 0)
        self.text_pw = QLineEdit(self)
        self.text_pw.textChanged.connect(self.changed)
        self.text_pw.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.text_pw, 1, 1)

        self.btn_ok = QPushButton("OK", self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.ok_click)
        btn_quit = QPushButton("Quit", self)
        btn_quit.clicked.connect(self.reject)
        grid.addWidget(btn_quit, 2, 0)
        grid.addWidget(self.btn_ok, 2, 1)

        self.setLayout(grid)
        self.changed()
        self.show()

        self.lims_url = lims_url

    def lims_init(self):
        global lims
        lims = Lims(self.lims_url, self.text_user.text(), self.text_pw.text())
        try:
            lims.check_version()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                QMessageBox.warning(self, "LIMS error", "Invalid username or password for "
                        + str(self.lims_url))
            return False
        except Exception as e:
            return False
        
    def ok_click(self):
        if self.lims_init():
            self.accept()
            self.finishLogin.emit()

    def reject(self):
        super().reject()
        QCoreApplication.instance().quit()

    def changed(self):
        self.btn_ok.setEnabled(bool(self.text_user.text() and self.text_pw.text()))


class LimsImporter(QWidget):
    def __init__(self, lims_url):
        super().__init__()
        self.resize(320, 240)
        self.setWindowTitle("LIMS project import tool")
        icon = QIcon("rocket.png")
        self.setWindowIcon(icon)

        self.show()

        self.list = QListWidget(self)
        #self.list.setSize(300, 200)
        self.login_box = LoginBox(self, lims_url)

    def refresh(self):
        pass


if __name__ == "__main__":
    a = QApplication(sys.argv)
    if len(sys.argv) > 1:
        lims_url = sys.argv[1]
    else:
        lims_url = "https://ous-lims.sequencing.uio.no/"
    w = LimsImporter(lims_url)
    a.setActiveWindow(w.login_box)
    w.raise_()
    sys.exit(a.exec_())

