import os
import argparse
import sys

from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QCheckBox, QPushButton, QVBoxLayout
from PyQt5.QtCore import Qt

from modules.io import io_profile
from modules.io import io_global
from modules.io import io_go

from modules.sync import check_and_sync_saves
from modules.sync import upload_dialog

from components.config_dialog import show_config_dialog

import modules.paths as paths
script_dir = paths.script_dir
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file
game_overrides_config_file = paths.game_overrides_config_file
python_exe_path = paths.python_exe_path

with open('debug.log', 'w'):
    pass


class RiskWarningDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Unstable Build Warning")
        self.setFixedSize(400, 150)

        self.label = QLabel("This is an unstable build of the program which is likely to be broken in many ways. Use at your own risk and always make personal backups of everything you point this at.", self)
        self.label.setWordWrap(True)

        self.checkbox = QCheckBox("I acknowledge the risk", self)
        self.checkbox.stateChanged.connect(self.on_checkbox_state_changed)

        self.ok_button = QPushButton("OK", self)
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.ok_button)

    def on_checkbox_state_changed(self, state):
        self.ok_button.setEnabled(state == Qt.Checked)

    def closeEvent(self, event):
        sys.exit(1)


def show_risk_warning_if_needed():
    risk_acknowledged = io_global("read", "config", "risk_acknowledged")
    if risk_acknowledged is not None:
        return

    dialog = RiskWarningDialog()
    if dialog.exec() == QDialog.Accepted:
        io_global("write", "config", "risk_acknowledged", "1")


# Parse command-line arguments
parser = argparse.ArgumentParser()

parser.add_argument("--runprofile", help="Specify the game profile name to be used")
parser.add_argument("--runid", help="Specify the profile ID to be used")

args = parser.parse_args()

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

app = QApplication([])

profile_data = None

cloud_storage_path = io_global("read", "config", "cloud_storage_path")

if args.runprofile:
    profile_id_list = io_profile("read", None, "profile", "name", args.runprofile)
    if len(profile_id_list) > 1:
        print("Conflict: There are multiple profiles with the same name. Aborting.")
        sys.exit(1)
    elif profile_id_list:
        profile_id = profile_id_list[0]
    else:
        profile_id = None
    if not profile_id:
        print("The specified game profile does not exist in profiles.ini")
        sys.exit(1)
    show_risk_warning_if_needed()
    app.setQuitOnLastWindowClosed(False)
    check_and_sync_saves(profile_id)
    
elif args.runid:
    if not cloud_storage_path:
        print("Cloud storage path is not configured. Run the script without a parameter to run the first-time setup")
        sys.exit(1)
    if not os.path.exists(cloud_storage_path):
        print("Cloud storage path is invalid. Run the configuration tool to fix.")
        sys.exit(1)
    profile_id = args.runid
    profile_fields = io_profile("read", profile_id)
    if not profile_fields:
        print("Profile ID not found. Aborting.")
        sys.exit(1)
    profile_fields = io_profile("read", profile_id, "profile")
    name = profile_fields.get("name")
    game_executable = profile_fields.get("game_executable")
    local_save_folder = profile_fields.get("local_save_folder")
    save_slot = profile_fields.get("save_slot")
    sync_mode = profile_fields.get("sync_mode")
    cloud_profile_folder = os.path.join(cloud_storage_path, f"{profile_id}")

    # Profile validity code to go here

    show_risk_warning_if_needed()
    app.setQuitOnLastWindowClosed(False)
    check_and_sync_saves(profile_id)

else:
    show_risk_warning_if_needed()
    app.setQuitOnLastWindowClosed(True)
    show_config_dialog()

app.exec_()