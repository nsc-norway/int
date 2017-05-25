import sys
import os
import requests
import glob
import json
import contextlib
import datetime
import base64
import re
from genologics.lims import *
from implib import *

lims = None



class LimsImportMainWindow(QWidget):
    def __init__(self, lims_url):
        super().__init__()
        self.resize(500, 240)
        self.setWindowTitle("LIMS project import tool")
        icon = QIcon("rocket.png")
        self.setWindowIcon(icon)

        vbox = QVBoxLayout()
        topbox = QHBoxLayout()

        self.path_box = QLineEdit(self)
        self.path_box.setText(self.get_default_path())
        self.path_btn = QPushButton("Choose directory...", self)
        self.path_btn.clicked.connect(self.path_dialog)
        self.refresh_btn = QPushButton("Refresh", self)
        self.refresh_btn.clicked.connect(self.load_file_list)
        topbox.addWidget(self.path_box)
        topbox.addWidget(self.path_btn)
        topbox.addWidget(self.refresh_btn)
        vbox.addLayout(topbox)

        self.list = QListWidget(self)
        vbox.addWidget(self.list)

        botbox = QHBoxLayout()

        self.quit_btn = QPushButton("Quit", self)
        self.quit_btn.clicked.connect(QCoreApplication.instance().quit)
        botbox.addWidget(self.quit_btn)
        self.delete_check = QCheckBox("Delete file(s) when imported", self)
        self.delete_check.setChecked(True)
        botbox.addWidget(self.delete_check)
        self.import_btn = QPushButton("Import", self)
        self.import_btn.clicked.connect(self.import_projects)
        botbox.addWidget(self.import_btn)
        vbox.addLayout(botbox)
        self.setLayout(vbox)
        self.load_file_list()
        self.show()

    def get_default_path(self):
        """Gets the last valid drive letter in a range as default"""

        path = os.path.expanduser("~")
        for drive_letter in "DEFGHIJKL":
            test = "{0}:\\".format(drive_letter)
            if os.path.exists(test):
                path = test
        return path

    def path_dialog(self):
        self.path_box.setText(
                QFileDialog.getExistingDirectory(self, "Select directory", self.path_box.text())
                )
        self.load_file_list()

    def load_file_list(self):
        self.showing_dir_path = self.path_box.text()
        self.list.clear()
        for p in sorted(glob.glob(os.path.join(self.showing_dir_path, "*.order"))):
            basename = os.path.basename(p)
            item = QListWidgetItem(basename, self.list)
            item.setFlags(Qt.ItemIsUserCheckable | item.flags())
            item.setCheckState(Qt.Checked)


    def import_projects(self):
        project_list = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.Checked:
                project_list.append(item)
        project_names = [p.text() for p in project_list]
        lim = ImporterProgressWindow(self, project_names, Importer.JOBS)
        paths = [os.path.join(self.showing_dir_path, p.text()) for p in project_list]
        importer = Importer(lim, paths)
        if importer.run():
            if self.delete_check.checkState == Qt.Checked:
                for p in paths:
                    os.path.remove(p)
                self.load_file_list()
        lim.set_complete()

    def lims_init(self):
        global lims
        lims = Lims(self.lims_url, self.text_user.text(), self.text_pw.text())
        try:
            lims.check_version()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                QMessageBox.warning(self, "LIMS error",
                        "Invalid username or password.")
            return False
        except Exception as e:
            QMessageBox.warning(self, "LIMS connection error",
                    "Unable to connect to LIMS because of the following "
                    "error: " + str(type(e)) + ": " + str(e))
            return False


if __name__ == "__main__":
    a = QApplication(sys.argv)
    if len(sys.argv) > 1:
        lims_url = sys.argv[1]
    else:
        lims_url = "https://sandbox-lims.sequencing.uio.no/"
    w = LimsImportMainWindow(lims_url)
    a.setActiveWindow(w)
    sys.exit(a.exec_())

