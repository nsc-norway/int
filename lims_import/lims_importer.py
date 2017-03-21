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
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5.QtCore import QCoreApplication, pyqtSignal, Qt, QAbstractItemModel


lims = None
lims = Lims("https://sandbox-lims.sequencing.uio.no", "paalmbj", open("pass.txt").read().strip())

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
        
        self.status_text = QLabel("")
        grid.addWidget(self.status_text, 2, 1)

        self.btn_ok = QPushButton("OK", self)
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.ok_click)
        btn_quit = QPushButton("Quit", self)
        btn_quit.clicked.connect(self.reject)
        grid.addWidget(btn_quit, 3, 0)
        grid.addWidget(self.btn_ok, 3, 1)

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
                QMessageBox.warning(self, "LIMS error",
                        "Invalid username or password.")
            return False
        except Exception as e:
            QMessageBox.warning(self, "LIMS connection error",
                    "Unable to connect to LIMS because of the following "
                    "error: " + str(type(e)) + ": " + str(e))
            return False
        
    def ok_click(self):
        self.status_text.setText("Logging in...")
        self.set_inputs_enabled(False)
        QCoreApplication.instance().processEvents()
        if self.lims_init():
            self.accept()
            self.finishLogin.emit()
        else:
            self.status_text.setText("")
            self.set_inputs_enabled(True)

    def set_inputs_enabled(self, enabled):
        self.btn_ok.setEnabled(enabled)
        self.text_user.setEnabled(enabled)
        self.text_pw.setEnabled(enabled)

    def reject(self):
        super().reject()
        QCoreApplication.instance().quit()

    def changed(self):
        self.btn_ok.setEnabled(bool(self.text_user.text() and self.text_pw.text()))


class ImporterProgressWindow(QDialog):
    def __init__(self, parent, projects, jobs):
        super().__init__(parent)
        self.setWindowTitle("Importing projects...")
        self.resize(700, 500)
        vbox = QVBoxLayout()
        self.treewidget = QTreeWidget(self)
        self.treewidget.setColumnCount(2)
        vbox.addWidget(self.treewidget)
        self.close_button = QPushButton("Close", self)
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        vbox.addWidget(self.close_button)
        self.setLayout(vbox)
        self.projects = projects
        self.project_items = []
        self.job_items = []
        self.jobs = jobs
        self.init_status_tree()
        self.setModal(True)
        self.show()
        self.style = QCoreApplication.instance().style()
        self.active_project = None

    def init_status_tree(self):
        self.project_items = []
        self.job_items = []
        blank_pix = QPixmap(16, 16)
        blank_pix.fill(QColor(255, 255, 255, 0))
        blank = QIcon(blank_pix)
        for project in self.projects:
            project_item = QTreeWidgetItem(self.treewidget, [project, ""])
            project_item.setFlags(Qt.NoItemFlags)
            project_item.setIcon(0, blank)
            project_jobs = []
            for job in self.jobs:
                job_item = QTreeWidgetItem(project_item, [job, ""])
                job_item.setFlags(Qt.NoItemFlags)
                job_item.setIcon(0, blank)
                project_jobs.append(job_item)
            self.job_items.append(project_jobs)
            self.project_items.append(project_item)
        self.treewidget.resizeColumnToContents(0)
        self.treewidget.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.treewidget.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

    def set_active_project(self, index):
        self.project_items[index].setExpanded(True)
        self.project_items[index].setDisabled(False)
        self.active_project = index

    def set_project_result(self, index, error_flag, message=""):
        if not error_flag:
            self.project_items[index].setIcon(0, self.style.standardIcon(self.style.SP_DialogYesButton))
            self.project_items[index].setExpanded(False)
        self.project_items[index].setText(1, message)

    @contextlib.contextmanager
    def job_status(self, i_job):
        job = self.job_items[self.active_project][i_job]
        job.setDisabled(False)
        job.setIcon(0, self.style.standardIcon(self.style.SP_ArrowRight))
        self.treewidget.setCurrentItem(job)
        QCoreApplication.instance().processEvents()
        try:
            yield
        except Exception as e:
            job.setIcon(0, self.style.standardIcon(self.style.SP_DialogNoButton))
            job.setText(1, str(e))
            self.set_project_result(self.active_project, True)
            raise LoggedException(e)
        else:
            job.setIcon(0, self.style.standardIcon(self.style.SP_DialogYesButton))
        finally:
            QCoreApplication.instance().processEvents()

    def set_complete(self):
        # Scroll to bottom (in case of errors)
        self.treewidget.setCurrentItem(self.job_items[-1][-1])
        self.close_button.setEnabled(True)


class LoggedException(Exception):
    def __init__(self, cause):
        super().__init__()
        self.cause = cause


class ImporterException(Exception):
    pass


class Importer(object):

    JOBS = [
            "Read package file",
            "Check for existing project",
            "Create project",
            "Upload files",
            "Create samples",
            "Set indexes",
            "Assign to workflow"
            ]
    JOB_IDS = dict((j, i) for i, j in enumerate(JOBS))

    def __init__(self, status_monitor, paths):
        self.status_monitor = status_monitor
        self.paths = paths

    def run(self):
        all_ok = True
        for i, path in enumerate(self.paths):
            try:
                self.status_monitor.set_active_project(i)
                with self.status_monitor.job_status(self.JOB_IDS['Read package file']):
                    with open(path) as f:
                        package = json.load(f)
                    try:
                        project_name = package['title']
                        portal_id = package['iuid']
                        fields = package['fields']
                        files = package['files']
                        samples = fields.get('samples')
                        if not samples:
                            samples = fields['samples'] # TODO: alternative tables
                    except KeyError as e:
                        raise ImporterError("Missing required field: " + str(e))

                with self.status_monitor.job_status(self.JOB_IDS['Check for existing project']):
                    projects = lims.get_projects(udf={'Portal ID': portal_id})
                    if projects:
                        raise ImporterException("Existing project(s) " +
                                ", ".join(project.name for project in projects) +
                                " has same portal-ID.")
                    projects = lims.get_projects(name=project_name)
                    if projects:
                        raise ImporterException("A project with name '" + project_name +
                                    "' already exists.")

                with self.status_monitor.job_status(self.JOB_IDS['Create project']):
                    project = self.create_lims_project(project_name, portal_id, fields)

                with self.status_monitor.job_status(self.JOB_IDS['Upload files']):
                    for file in files:
                        gls = lims.glsstorage(project, file['filename'])
                        f_obj = gls.post()
                        data = base64.b64decode(file['data'])
                        f_obj.upload(data)

                with self.status_monitor.job_status(self.JOB_IDS['Create samples']):
                    is_libraries = not 'samples' in fields
                    self.create_samples(project, samples, is_libraries)

                with self.status_monitor.job_status(self.JOB_IDS['Set indexes']):
                    pass

                with self.status_monitor.job_status(self.JOB_IDS['Assign to workflow']):
                    pass

            except LoggedException:
                all_ok = False# Continue to next project
        return all_ok


    def create_lims_project(self, project_name, portal_id, fields):
        users = lims.get_researchers(username=lims.username)
        try:
            user = users[0]
        except IndexError:
            raise ImporterError("User '" + lims.username + "' not found!")
        read_length_fields = [
                "read_length_h2500",
                "read_length_h2500_rapid",
                "read_length_4000",
                "read_length_hX",
                "read_length_nextseq_mid",
                "read_length_nextseq_high",
                "read_length_miseq"
                ]
        read_length = 0
        for field in read_length_fields:
            val = fields.get(field)
            if val:
                read_length = int(re.match(r"(\d)+", val).group(0)) 
                break

        udfs = {
                'Project type': 'Sensitive' if fields['sensitive_data'] else 'Non-sensitive',
                'Method used to purify DNA/RNA': fields['purify_method'],
                'Method used to determine concentration': fields['concentration_method'],
                'Sample buffer': fields['buffer'],
                'Sample prep requested': fields.get('rna_sample_preps') or fields.get('dna_sample_prep') or 'None',
                'Species': fields['species'],
                'Reference genome': fields['reference_genome'],
                'Sequencing method': fields['sequencing_type'],
                'Desired insert size': fields['insert_size'],
                'Sequencing instrument requested': fields['sequencing_instrument'],
                'Read length requested': read_length,
                'Portal ID': portal_id
                }
        return lims.create_project(
                name=project_name,
                researcher=user,
                open_date=datetime.date.today(),
                udf=udfs
                )

    def create_samples(self, project, samples, is_libraries):
        containers = {}
        if all('position' in sample for sample in samples) and \
                all('plate' in sample for sample in samples):
            container_96 = lims.get_container_types(name="96 well plate")[0]
            for plate in set(sample['plate'] for sample in samples):
                containers[plate] = lims.create_container(type=container_96, name=plate)
        for i, sample in enumerate(samples, 1):
            sample_name = i
            try:
                sample_name = sample[2]
                container = containers.get(sample[0]) # container=None creates a Tube!
                position = "{0}:{1}".format(sample[1][0], sample[1][1:])
                if is_libraries:
                    udf = {}
                else:
                    udf = {
                            'Sample conc. (ng/ul)': sample[3],
                            'A260/280': sample[4],
                            'A260/230': sample[5],
                            'Volume (ul)': sample[6]
                            }
                lims.create_sample(sample_name, project, container, position, udf)
            except IndexError as e:
                raise ImporterError("Missing data for sample " + str(sample_name) + " -- import aborted")


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


if __name__ == "__main__":
    a = QApplication(sys.argv)
    if len(sys.argv) > 1:
        lims_url = sys.argv[1]
    else:
        lims_url = "https://ous-lims.sequencing.uio.no/"
    w = LimsImportMainWindow(lims_url)
    #a.setActiveWindow(w.login_box)
    #w.raise_()
    sys.exit(a.exec_())

