import contextlib

from PyQt5.QtWidgets import QDialog, QWidget, QFileDialog,\
                        QPushButton, QLineEdit, QCheckBox, QLabel, QListWidget, QListWidgetItem, QTreeWidget,\
                        QTreeWidgetItem, QHeaderView,\
                        QGridLayout, QHBoxLayout, QVBoxLayout,\
                        QMessageBox, QApplication
from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5.QtCore import QCoreApplication, pyqtSignal, Qt, QAbstractItemModel



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

    def __init__(self, status_monitor, paths=None, packages=None):
        self.status_monitor = status_monitor
        self.packages = packages
        self.paths = paths

    def run(self):
        all_ok = True
        if self.packages:
            data = self.packages
        else:
            data = self.paths 
        for i, datum in enumerate(data):
            try:
                self.status_monitor.set_active_project(i)
                with self.status_monitor.job_status(self.JOB_IDS['Read package file']):
                    if self.packages:
                        package = datum
                    else:
                        with open(datum) as f:
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

