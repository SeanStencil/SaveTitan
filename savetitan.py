import os
import shutil
import filecmp
import subprocess
import configparser
import argparse
import hashlib
import random
import string
import datetime
import sys
import glob
import stat
import logging
import socket
import json
import re


from configparser import ConfigParser
from xml.etree import ElementTree
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QInputDialog, QMenu, QAction, QDialog, QListWidgetItem
from PyQt5.QtGui import QIcon, QDesktopServices, QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QTimer, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QUrl


# Get the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))


# Define the config file path
profiles_config_file = os.path.join(script_dir, "user/profiles")
global_config_file = os.path.join(script_dir, "global.ini")


# Generate a 8 character string for use for profile_id's
def generate_id():
    characters = string.ascii_lowercase + string.digits
    id_length = 8
    random_id = ''.join(random.choices(characters, k=id_length))
    return random_id


# Check a function's ability to perform the given action (read, write, execute) on the file/folder path
def check_permissions(path, file_type, action):
    actions = {
        "read": os.R_OK,
        "write": os.W_OK,
        "execute": os.X_OK
    }

    if not os.path.exists(path):
        return True

    if not os.access(path, actions[action]):
        QMessageBox.critical(None, "Access Denied",
                             f"Permission denied to {action} the {file_type}. Please check the file permissions and try again.")
        return False
    return True


# Try and wake up the network location
def network_share_accessible():
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    if cloud_storage_path is None:
        QMessageBox.critical(None, "Cloud Storage Path Not Found", "Cloud storage path is not configured. Please configure it.")
        return False

    cloud_storage_path = cloud_storage_path.replace("\\", "\\\\")

    if check_permissions(cloud_storage_path, 'cloud storage', "read"):
        return True
    else:
        QMessageBox.critical(None, "Network Error",
                             f"An error occurred while trying to access the network share: Permission denied.")
        return False


def io_profile(read_write_mode, profile_id=None, section=None, field=None, value=None):
    read_write_mode = str(read_write_mode)
    profile_id = str(profile_id) if profile_id is not None else None
    section = str(section) if section is not None else None
    field = str(field) if field is not None else None
    value = str(value) if value is not None else None

    if read_write_mode == "read":

        if profile_id and section and field:
            config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
            if not os.path.exists(config_file):
                return None
            config = ConfigParser()
            config.read(config_file)
            if config.has_option(section, field):
                return config.get(section, field)

        elif profile_id and section:
            config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
            if not os.path.exists(config_file):
                return None
            config = ConfigParser()
            config.read(config_file)
            if config.has_section(section):
                return dict(config.items(section))

        elif section and field and value:
            matching_profiles = []
            for file in glob.glob(os.path.join(profiles_config_file, '*.ini')):
                config = ConfigParser()
                config.read(file)
                file_id = os.path.splitext(os.path.basename(file))[0]
                if config.has_option(section, field) and config.get(section, field).lower() == value.lower():
                    matching_profiles.append(file_id)
            return matching_profiles

        elif section:
            profiles_data = {}
            for file in glob.glob(os.path.join(profiles_config_file, '*.ini')):
                config = ConfigParser()
                config.read(file)
                file_id = os.path.splitext(os.path.basename(file))[0]
                if config.has_section(section):
                    profiles_data[file_id] = dict(config.items(section))
            return profiles_data
        else:
            return [os.path.splitext(os.path.basename(file))[0] for file in glob.glob(os.path.join(profiles_config_file, '*.ini'))]

    elif read_write_mode == "write":
        if not profile_id or not section or not field:
            raise ValueError("For 'write' mode, profile_id, section, and field must be specified.")

        config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
        config = ConfigParser()
        if os.path.exists(config_file):
            config.read(config_file)
        if not config.has_section(section):
            config.add_section(section)

        config.set(section, field, value if value is not None else "")
        with open(config_file, "w") as file:
            config.write(file)

    elif read_write_mode == "delete":
        if not profile_id:
            raise ValueError("For 'delete' mode, profile_id must be specified.")

        config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
        if os.path.exists(config_file):
            os.remove(config_file)
        else:
            raise FileNotFoundError(f"No profile found with ID: {profile_id}")

    else:
        raise ValueError("Invalid mode. Expected 'read', 'write', or 'delete'.")

 
def io_global(read_write_mode, section=None, field=None, value=None):
    read_write_mode = str(read_write_mode)
    section = str(section) if section is not None else None
    field = str(field) if field is not None else None
    value = str(value) if value is not None else None
    config = ConfigParser()

    if read_write_mode == "read":
        if not section or not field:
            raise ValueError("For 'read' mode, section and field must be specified.")

        config.read(global_config_file)
        if config.has_option(section, field):
            return config.get(section, field)
        else:
            raise KeyError(f"No such field '{field}' in section '{section}' in global.ini.")

    elif read_write_mode == "write":
        if not section or not field:
            raise ValueError("For 'write' mode, section and field must be specified.")

        if not config.has_section(section):
            config.add_section(section)

        config.set(section, field, value if value is not None else "")
        with open(global_config_file, "w") as file:
            config.write(file)

    else:
        raise ValueError("Invalid mode. Expected 'read' or 'write'.")


def io_savetitan(read_write_mode, profile_id, section, field=None, write_value=None):
    profile_id = str(profile_id)
    section = str(section)
    if field is not None:
        field = str(field)
    if write_value is not None:
        write_value = str(write_value)
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    if cloud_storage_path is None:
        raise ValueError("Cloud storage path is not defined.")
        
    profile_info_path = os.path.join(cloud_storage_path, profile_id, "profile_info.savetitan")

    config = configparser.ConfigParser()
    config.read(profile_info_path)

    if read_write_mode == "read":
        if field:
            if config.has_option(section, field):
                return config.get(section, field)
            else:
                return None
        else:
            if config.has_section(section):
                return dict(config.items(section))
            else:
                return None
    elif read_write_mode == "write":
        if not field:
            raise ValueError("For write operation, field is required.")
        
        if not config.has_section(section):
            config.add_section(section)

        write_value = "" if write_value is None else str(write_value)
        config.set(section, field, write_value)
        
        with open(profile_info_path, 'w') as configfile:
            config.write(configfile)
    else:
        raise ValueError("Invalid operation. Expected 'read' or 'write'.")


# Checks for file mismatch
def check_folder_mismatch(folder_a, folder_b):
    comparison = filecmp.dircmp(folder_a, folder_b)

    def compare_dirs(comp):
        if comp.diff_files or comp.left_only or comp.right_only or comp.funny_files:
            return True

        match, mismatch, errors = filecmp.cmpfiles(comp.left, comp.right, comp.common_files, shallow=False)
        if mismatch or errors:
            return True

        for subcomp in comp.subdirs.values():
            if compare_dirs(subcomp):
                return True

        return False

    return compare_dirs(comparison)


# Function to sync saves (Copy local saves to cloud storage)
def sync_save_cloud(profile_id):
    local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    save_slot = io_profile("read", profile_id, "profile", "save_slot")

    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)

    if not network_share_accessible():
        return
        
    while True:
        try:
            os.makedirs(cloud_profile_save_path, exist_ok=True)
            
            make_backup_copy(profile_id, "cloud_backup")
            
            shutil.rmtree(cloud_profile_save_path)
            shutil.copytree(local_save_folder, cloud_profile_save_path)
            
            if check_folder_mismatch(local_save_folder, cloud_profile_save_path):
                raise Exception("Mismatch in directory contents")
            else:
                print("Sync completed successfully.")
                break
        except Exception as e:
            reply = QMessageBox.critical(None, "Sync Error",
                                         f"An error occurred during the sync process: {str(e)}",
                                         QMessageBox.Retry | QMessageBox.Abort, QMessageBox.Retry)
            if reply != QMessageBox.Retry:
                break


# Function to sync saves (Copy cloud saves to local storage)
def sync_save_local(profile_id):
    local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    save_slot = io_profile("read", profile_id, "profile", "save_slot")
    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)

    if not network_share_accessible():
        return

    while True:
        try:
            os.makedirs(local_save_folder, exist_ok=True)

            make_backup_copy(profile_id, "local_backup")

            shutil.rmtree(local_save_folder)
            shutil.copytree(cloud_profile_save_path, local_save_folder)

            if check_folder_mismatch(cloud_profile_save_path, local_save_folder):
                raise Exception("Mismatch in directory contents")
            else:
                print("Sync completed successfully.")
                break
        except Exception as e:
            reply = QMessageBox.critical(None, "Sync Error",
                                         f"An error occurred during the sync process: {str(e)}",
                                         QMessageBox.Retry | QMessageBox.Abort, QMessageBox.Retry)
            if reply != QMessageBox.Retry:
                break


# Perform backup function prior to sync
def make_backup_copy(profile_id, which_side):
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    save_slot = io_profile("read", profile_id, "profile", "save_slot")
    cloud_profile_folder_save = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)
    cloud_profile_folder_save_bak = cloud_profile_folder_save + ".bak"

    if which_side not in ["local_backup", "cloud_backup"]:
        raise Exception("Invalid which_side argument")

    os.makedirs(cloud_profile_folder_save_bak, exist_ok=True)

    if which_side == "local_backup":
        local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
        
        if os.path.exists(cloud_profile_folder_save_bak):
            shutil.rmtree(cloud_profile_folder_save_bak)

        shutil.copytree(local_save_folder, cloud_profile_folder_save_bak)

    elif which_side == "cloud_backup":
        if os.path.exists(cloud_profile_folder_save_bak):
            shutil.rmtree(cloud_profile_folder_save_bak)

        shutil.copytree(cloud_profile_folder_save, cloud_profile_folder_save_bak)


def export_profile_info(profile_name, profile_id, sync_mode, executable_name):
    if not network_share_accessible():
        QMessageBox.critical(None, "Add Profile Aborted",
                             "The network location is not accessible, the process to add the profile has been aborted.")
        return

    folder_path = os.path.join(cloud_storage_path, profile_id)
    os.makedirs(folder_path, exist_ok=True)

    save1_folder_path = os.path.join(folder_path, 'save1')
    os.makedirs(save1_folder_path, exist_ok=True)

    profile_info_fields = [
        ("name", profile_name),
        ("save_slot", "1"),
        ("saves", "1"),
        ("sync_mode", sync_mode),
        ("executable_name", executable_name),
        ("checkout", "")
    ]

    for field, value in profile_info_fields:
        io_savetitan("write", profile_id, "profile", field, value)

    io_savetitan("write", profile_id, "saves", "save1", "Save 1")


# Function to check and sync saves
def check_and_sync_saves(profile_id):
    #Load data set
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_fields = io_profile("read", profile_id, "profile")

    name = profile_fields.get("name")
    game_executable = profile_fields.get("game_executable")
    local_save_folder = profile_fields.get("local_save_folder")
    save_slot = profile_fields.get("save_slot")
    sync_mode = profile_fields.get("sync_mode")

    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id, "save" + save_slot)

    if sync_mode != "Sync":
        launch_game_without_sync(game_executable)
        return

    # Check: Checkout Hostname
    checkout_previous_user = io_savetitan("read", profile_id, "profile", "checkout")
    checkout_current_user = socket.gethostname()
    if checkout_previous_user and checkout_previous_user != checkout_current_user:
        checkout_msgbox = QMessageBox()
        checkout_msgbox.setWindowTitle("Checkout Warning")
        checkout_msgbox.setText(
            f"Someone started playing from \"{checkout_previous_user}\" and hasn't synced yet. (This can happen if the other computer didn't close SaveTitan through normal operation)\n\n"
            f""
            f"Do you want to continue?"
        )
        yes_button = checkout_msgbox.addButton(QMessageBox.Yes)
        no_button = checkout_msgbox.addButton(QMessageBox.No)
        checkout_msgbox.setDefaultButton(no_button)
        result = checkout_msgbox.exec_()

        if result == -1 or checkout_msgbox.clickedButton() == no_button:
            sys.exit()
        elif checkout_msgbox.clickedButton() == yes_button:
            io_savetitan("write", profile_id, "profile", "checkout", checkout_current_user)

    elif not checkout_previous_user:
        io_savetitan("write", profile_id, "profile", "checkout", checkout_current_user)

    # Check: If files with the same name are identical
    print("comparing: ", cloud_profile_save_path, " with ", cloud_profile_save_path)

    if os.path.exists(cloud_profile_save_path) and os.listdir(cloud_profile_save_path):
        files_identical = True
        for dirpath, dirnames, filenames in os.walk(local_save_folder):
            for filename in filenames:
                local_file = os.path.join(dirpath, filename)
                cloud_file = os.path.join(cloud_profile_save_path, os.path.relpath(local_file, local_save_folder))
                if os.path.exists(cloud_file):
                    if not filecmp.cmp(local_file, cloud_file, shallow=False):
                        files_identical = False
                        break
                else:
                    files_identical = False
                    break
            if not files_identical:
                break

        # Check: If files indentical, tally the amount of files
        if files_identical:
            local_files_count = len(os.listdir(local_save_folder))
            cloud_files_count = len(os.listdir(cloud_profile_save_path))
            
            # Result: More local files than cloud - Action: Copy contents of local folder to cloud
            if local_files_count > cloud_files_count:
                launch_game(profile_id)
                
            # Result: More cloud files than local - Action: Copy contents of cloud folder to local
            elif cloud_files_count > local_files_count:
                sync_save_local(profile_id)
                launch_game(profile_id)
                
            # Result: Content and amount of files is identical - Action: Launch the game, upload when done
            else:
                launch_game(profile_id)

        # Result: Files aren't identical - Action: Compare files to find latest timestamp
        else:
            local_file_time = datetime(1900, 1, 1)
            cloud_file_time = datetime(1900, 1, 1)

            for dirpath, dirnames, filenames in os.walk(local_save_folder):
                for filename in filenames:
                    file_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filename)))
                    if local_file_time < file_time:
                        local_file_time = file_time
                           
            for dirpath, dirnames, filenames in os.walk(cloud_profile_save_path):
                for filename in filenames:
                    file_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filename)))
                    if cloud_file_time < file_time:
                        cloud_file_time = file_time

            local_save_time_str = local_file_time.strftime("%B %d, %Y, %I:%M:%S %p")
            cloud_save_time_str = cloud_file_time.strftime("%B %d, %Y, %I:%M:%S %p")

            # Draw sync dialog
            sync_diag = uic.loadUi("sync_diag.ui")
            sync_diag.local_date.setText(local_save_time_str)
            sync_diag.cloud_date.setText(cloud_save_time_str)

            config_profiles = io_profile("read", profile_id, "profile")
            game_name = config_profiles.get(profile_id, 'name')

            sync_diag.setWindowTitle(game_name)
            if cloud_file_time > local_file_time:
                sync_diag.local_indication.setText("Local Copy: Older")
                sync_diag.cloud_indication.setText("Cloud Copy: Newer")
            else:
                sync_diag.local_indication.setText("Local Copy: Newer")
                sync_diag.cloud_indication.setText("Cloud Copy: Older")

            def on_nosyncButton_clicked():
                launch_game_without_sync(profile_id)
                io_savetitan("write", profile_id, "profile", "checkout", None)
                sync_diag.accept()
            
            def on_rejected_connect():
                io_savetitan("write", profile_id, "profile", "checkout", None)
                sys.exit()

            sync_diag.downloadButton.clicked.connect(lambda: [sync_save_local(profile_id), launch_game(profile_id), sync_diag.accept()])
            sync_diag.uploadButton.clicked.connect(lambda: [launch_game(profile_id), sync_diag.accept()])
            sync_diag.nosyncButton.clicked.connect(lambda: [on_nosyncButton_clicked()])

            sync_diag.rejected.connect(lambda: on_rejected_connect())
            
            sync_diag.exec_()
    else:
        launch_game(profile_id)


# Function to launch the game
def launch_game(profile_id):
    game_executable = io_profile("read", profile_id, "profile", "game_executable")
    profile_info_savetitan_path = os.path.join(cloud_storage_path, profile_id + "/profile_into.savetitan")
    
    if not check_permissions(game_executable, 'game executable', "execute"):
        return

    subprocess.Popen(game_executable)

    def launch_game_dialog():
        message_box = QMessageBox()
        message_box.setWindowTitle("Game in Progress")
        message_box.setText("Please click 'Upload to Cloud' when you have finished playing.")
        
        done_button = message_box.addButton("Upload to Cloud", QMessageBox.AcceptRole)
        abort_button = message_box.addButton("Abort Sync", QMessageBox.RejectRole)
        
        message_box.exec_()

        if message_box.clickedButton() == done_button:
            sync_save_cloud(profile_id)

        io_savetitan("write", profile_id, "profile", "checkout")

    QTimer.singleShot(0, launch_game_dialog)


# Function to launch the game without sync
def launch_game_without_sync(game_executable):
    game_executable = io_profile("read", profile_id, "profile", "game_executable")
    profile_info_savetitan_path = os.path.join(cloud_storage_path, profile_id + "/profile_into.savetitan")
    
    if not check_permissions(game_executable, 'game executable', "execute"):
        return

    subprocess.Popen(game_executable)
    
    sys.exit()


# Function to set the cloud storage location
def set_cloud_storage_path():
    current_cloud_storage_path = io_global("read", "config", "cloud_storage_path") or ""
    if not os.path.isdir(current_cloud_storage_path):
        current_cloud_storage_path = ""

    while True:
        cloud_storage_path = QFileDialog.getExistingDirectory(None, "Select Cloud Storage Path", current_cloud_storage_path)
        if not cloud_storage_path:
            break

        if not os.path.exists(cloud_storage_path):
            QMessageBox.warning(None, "Invalid Path",
                                "The selected path does not exist. Please select another path.")
            continue

        subfolders = [f.path for f in os.scandir(cloud_storage_path) if f.is_dir()]
        savetitan_files_found = False
        for subfolder in subfolders:
            savetitan_files = glob.glob(os.path.join(subfolder, "*.savetitan"))
            if len(savetitan_files) > 0:
                savetitan_files_found = True
                break

        if savetitan_files_found:
            QMessageBox.information(None, "Existing SaveTitan Cloud Folder Detected",
                                    "This appears to be an existing SaveTitan cloud folder. "
                                    "Make sure to use the 'Import' button to import existing profiles.")
        elif not savetitan_files_found and len(os.listdir(cloud_storage_path)) > 0:
            response = QMessageBox.warning(None, "Non-Empty Cloud Storage Path",
                                           "WARNING: The selected cloud storage path is not empty. "
                                           "Would you like to create a new SaveTitan directory in it?",
                                           QMessageBox.Yes | QMessageBox.No)
            if response == QMessageBox.Yes:
                cloud_storage_path = os.path.join(cloud_storage_path, "SaveTitan")
                os.makedirs(cloud_storage_path, exist_ok=True)
            else:
                continue

        io_global("write", "config", "cloud_storage_path", cloud_storage_path)
        break

    dialog.addButton.setEnabled(True)
    dialog.importButton.setEnabled(True)


# Calculate the center position over another dialog window
def center_dialog_over_dialog(first_dialog, second_dialog):
    def move_second_dialog_to_center():
        first_dialog_size = first_dialog.size()
        first_dialog_loc = first_dialog.pos()

        second_dialog_size = second_dialog.frameGeometry()
        x = int(first_dialog_loc.x() + (first_dialog_size.width() - second_dialog_size.width()) / 2)
        y = int(first_dialog_loc.y() + (first_dialog_size.height() - second_dialog_size.height()) / 2)

        second_dialog.move(x, y)

    QTimer.singleShot(0, move_second_dialog_to_center)


# Function to show config dialog
def show_config_dialog():
    global dialog

    dialog = uic.loadUi("config.ui")
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)

    dialog.setFixedSize(dialog.size())

    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    if not cloud_storage_path:
        QMessageBox.warning(None, "Cloud Storage Path Not Set",
                            "The cloud storage path is not configured. SaveTitan won't function until a cloud storage path is set.")
        response = QMessageBox.question(None, "Set Cloud Storage Path",
                                        "Would you like to set the cloud storage path now?", QMessageBox.Yes | QMessageBox.No)
        if response == QMessageBox.Yes:
            set_cloud_storage_path()
    else:
        if not os.path.exists(cloud_storage_path):
            QMessageBox.warning(None, "Invalid Cloud Storage Path",
                                "The current cloud storage location is invalid.")
            io_global("write", "config", "cloud_storage_path")
            response = QMessageBox.question(None, "Set New Cloud Storage Path",
                                             "Would you like to set a new cloud storage path?", QMessageBox.Yes | QMessageBox.No)
            if response == QMessageBox.Yes:
                set_cloud_storage_path()
        elif not check_permissions(cloud_storage_path, 'Cloud Storage Path', 'write'):
            dialog.addButton.setEnabled(False)
            dialog.importButton.setEnabled(False)
            dialog.removeButton.setEnabled(False)
            dialog.actionNewProfile.setEnabled(False)
            dialog.actionRemoveProfile.setEnabled(False)
            dialog.actionImportProfile.setEnabled(False)


    def load_data_into_model_data():
        profile_ids = io_profile("read")
        data = []
        for profile_id in profile_ids:
            profile_data = io_profile("read", profile_id, "profile")
            if profile_data:
                name = profile_data.get("name")
                sync_mode = profile_data.get("sync_mode")
                row = [name, sync_mode, profile_id]
                data.append(row)
        return data
    

    class TableModel(QtCore.QAbstractTableModel):
        def __init__(self, data, headers):
            super(TableModel, self).__init__()
            self._data = data
            self.headers = headers

        def data(self, index, role):
            if role == Qt.DisplayRole:
                row_data = self._data[index.row()]
                column = index.column()
                if 0 <= column < len(row_data):
                    return row_data[column]

        def rowCount(self, index):
            return len(self._data)

        def columnCount(self, index):
            return len(self.headers)

        def headerData(self, section, orientation, role):
            if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return self.headers[section]

        def flags(self, index):
            flags = super(TableModel, self).flags(index)
            flags |= Qt.ItemIsEditable
            return flags

    configprofileView = dialog.findChild(QtWidgets.QTableView, "configprofileView")

    headers = ["Profile Name", "Mode", "Profile ID"]

    data = load_data_into_model_data()
                
    proxy_model = QSortFilterProxyModel()
    proxy_model.setSourceModel(TableModel(data, headers))
    proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
    proxy_model.setFilterKeyColumn(0)
        
    configprofileView.setModel(proxy_model)
        
    filter_field = dialog.findChild(QtWidgets.QLineEdit, "filterField")
    filter_field.textChanged.connect(lambda text: proxy_model.setFilterFixedString(text))

    header = configprofileView.horizontalHeader()

    header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
    header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

    configprofileView.resizeRowsToContents()

    if configprofileView.model().rowCount(QModelIndex()) > 0:
        selected_index = configprofileView.currentIndex()
        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        selected_profile_id = selected_row_data[2]


    # Open global settings dialog
    def global_settings_dialog():
        global_settings_dialog = QtWidgets.QDialog()
        global_settings_dialog.setWindowTitle("Global Settings")
        global_settings_dialog.setGeometry(100, 100, 300, 200)
        global_settings_dialog.setFixedSize(300, 200)

        cloud_storage_button = QtWidgets.QPushButton("Set Cloud Storage Path")
        cloud_storage_button.clicked.connect(set_cloud_storage_path)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(cloud_storage_button)
        global_settings_dialog.setLayout(layout)

        center_dialog_over_dialog(dialog, global_settings_dialog)

        global_settings_dialog.exec_()
        
        
    # Function to open save management dialog
    def save_mgmt_dialog(profile_id):
        save_mgmt_dialog = uic.loadUi("save_mgmt.ui")
        save_mgmt_dialog.setWindowFlags(save_mgmt_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        save_mgmt_dialog.setFixedSize(save_mgmt_dialog.size())

        profile_folder = os.path.join(cloud_storage_path, profile_id)

        save_mgmt_dialog.profilenameField.setText(io_savetitan("read", profile_id, "profile", "name"))
        save_mgmt_dialog.saveField.setText(io_profile("read", profile_id, "profile", "local_save_folder"))

        save_slot = io_profile("read", profile_id, "profile", "save_slot")
        save_slot_key = f"save{save_slot}"

        save_slot_name = io_savetitan("read", profile_id, "profile", "saves", save_slot_key)
        if save_slot_name:
            save_mgmt_dialog.saveslotField.setText(save_slot_name)

        center_dialog_over_dialog(QApplication.activeWindow(), save_mgmt_dialog)

        saves_data = io_savetitan("read", profile_id, "saves")
        if saves_data:
            for save_key, save_value in saves_data.items():
                item = QListWidgetItem(save_value)
                item.setData(Qt.UserRole, save_key)
                save_mgmt_dialog.save_listWidget.addItem(item)


        def handle_new_save_button():
            confirm_msg = QMessageBox()
            confirm_msg.setIcon(QMessageBox.Question)
            confirm_msg.setText("Would you like to create a new save slot?")
            confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_ret = confirm_msg.exec_()

            if confirm_ret == QMessageBox.No:
                return

            number_of_saves = int(io_savetitan("read", profile_id, "profile", "saves")) + 1
            io_savetitan("write", profile_id, "profile", "saves", str(number_of_saves))  # convert number_of_saves to string

            new_save_name = f"Save {number_of_saves}"
            io_savetitan("write", profile_id, "saves", f'save{number_of_saves}', new_save_name)

            new_save_folder = os.path.join(cloud_storage_path, profile_id, f'save{number_of_saves}')
            os.makedirs(new_save_folder, exist_ok=True)

            item = QListWidgetItem(new_save_name)
            item.setData(Qt.UserRole, f'save{number_of_saves}')
            save_mgmt_dialog.save_listWidget.addItem(item)


        def handle_load_save_button():
            selected_items = save_mgmt_dialog.save_listWidget.selectedItems()
            if not selected_items:
                return

            selected_item = selected_items[0]
            selected_save_key = selected_item.data(Qt.UserRole)

            current_save_slot = io_profile("read", profile_id, "profile", "save_slot")
            
            if selected_save_key == f"save{current_save_slot}":
                return

            local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
            cloud_save_folder = os.path.join(cloud_storage_path, profile_id, f"save{current_save_slot}")

            reply = QMessageBox.question(None, "Upload current save?",
                                        "Do you want to upload your current save before switching? Your local save will be replaced with the selected one.",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                sync_save_cloud(profile_id)

            new_save_slot = selected_save_key.replace('save', '')
            
            io_profile("write", profile_id, "profile", "save_slot", new_save_slot)

            save_mgmt_dialog.saveslotField.setText(selected_item.text())

            sync_save_local(profile_id)

            QMessageBox.information(None, "Load Finished", "The selected save has been loaded successfully.")


        # Handle delete save button click
        def handle_delete_save_button():
            selected_items = save_mgmt_dialog.save_listWidget.selectedItems()
            if not selected_items:
                return

            selected_item = selected_items[0]
            selected_save_key = selected_item.data(Qt.UserRole)

            confirm_msg = QMessageBox()
            confirm_msg.setIcon(QMessageBox.Question)
            confirm_msg.setText("Are you sure you want to delete this save? This will remove the save from the cloud storage.")
            confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_ret = confirm_msg.exec_()

            if confirm_ret == QMessageBox.No:
                return

            io_savetitan("delete", profile_id, "saves", selected_save_key)

            shutil.rmtree(os.path.join(cloud_storage_path, profile_id, selected_save_key))

            list_item = save_mgmt_dialog.save_listWidget.takeItem(save_mgmt_dialog.save_listWidget.row(selected_item))
            del list_item
                

        def handle_rename_save_button():
            selected_items = save_mgmt_dialog.save_listWidget.selectedItems()
            if not selected_items:
                return

            selected_item = selected_items[0]
            selected_save_key = selected_item.data(Qt.UserRole)

            new_save_name, ok = QInputDialog.getText(save_mgmt_dialog, "Rename Save", "Enter new save name:")
            if not ok or not new_save_name:
                return

            # Check if the new save name already exists
            saves_data = io_savetitan("read", profile_id, "saves")
            existing_save_names = [value.lower() for key, value in saves_data.items()]
            if new_save_name.lower() in existing_save_names:
                QMessageBox.warning(None, "Name Already Exists", "A save with this name already exists. Please choose a different name.")
                return

            io_savetitan("write", profile_id, "saves", selected_save_key, new_save_name)

            selected_item.setText(new_save_name)

        save_mgmt_dialog.newsaveButton.clicked.connect(handle_new_save_button)
        save_mgmt_dialog.loadsaveButton.clicked.connect(handle_load_save_button)
        save_mgmt_dialog.renamesaveButton.clicked.connect(handle_rename_save_button)
        save_mgmt_dialog.deletesaveButton.clicked.connect(handle_delete_save_button)

        save_mgmt_dialog.exec_()


    # Function to add a profile
    def add_profile():
        cloud_storage_path = io_global("read", "config", "cloud_storage_path")
        if not cloud_storage_path:
            QMessageBox.warning(None, "Cloud Storage Path Not Found", "Cloud storage path is not configured. Please configure it.")
            return

        if not os.path.exists(cloud_storage_path):
            return

        config_dialog = QApplication.activeWindow()
        add_profile_dialog = uic.loadUi("add_profile.ui")

        def select_executable():
            file_filter = "Executable Files (*.exe *.bat *.cmd)" if sys.platform == "win32" else "Executable Files (*.sh *.AppImage)"
            game_executable, ok = QFileDialog.getOpenFileName(None, "Select Executable", filter=file_filter)
            if ok:
                add_profile_dialog.executableField.setText(game_executable)

        add_profile_dialog.executablefieldButton.clicked.connect(select_executable)

        def select_save_directory():
            save_directory = QFileDialog.getExistingDirectory(None, "Select Save Directory")
            if save_directory:
                add_profile_dialog.saveField.setText(save_directory)

        add_profile_dialog.savefieldButton.clicked.connect(select_save_directory)

        center_dialog_over_dialog(config_dialog, add_profile_dialog)

        while True:
            result = add_profile_dialog.exec()
            if result == QDialog.Rejected:
                break

            profile_name = add_profile_dialog.profilefieldName.text()
            game_executable = add_profile_dialog.executableField.text()
            local_save_folder = add_profile_dialog.saveField.text()

            if not all([profile_name, game_executable, local_save_folder]):
                QMessageBox.warning(None, "Missing Data", "All fields must be filled.")
                continue

            if not os.path.exists(game_executable):
                QMessageBox.warning(None, "Invalid Executable", "The executable path is not valid.")
                continue
            if not os.path.isdir(local_save_folder):
                QMessageBox.warning(None, "Invalid Save Directory", "The save directory path is not valid.")
                continue

            if len(io_profile("read", None, "profile", "name", profile_name)) > 1:
                QMessageBox.critical(None, "Profile Already Exists", "A profile with the same name already exists. Please choose a different name.")
                continue

            sync_mode = "Sync" if add_profile_dialog.syncenableRadio.isChecked() else ""

            profile_id = None
            while True:
                profile_id = generate_id()
                if not io_profile("read", profile_id, "profile", "profile_id", profile_id):
                    break

            profile_folder = os.path.join(cloud_storage_path, profile_id)
            os.makedirs(profile_folder, exist_ok=True)

            export_profile_info(profile_name, profile_id, sync_mode, os.path.basename(game_executable))

            profile_fields = {
                "name": profile_name,
                "local_save_folder": local_save_folder,
                "game_executable": game_executable,
                "save_slot": "1",
                "saves": "1",
                "sync_mode": sync_mode,
            }

            for field, value in profile_fields.items():
                io_profile("write", profile_id, "profile", field, value)

            new_row_data = [profile_name, sync_mode, profile_id]
            configprofileView.model().sourceModel()._data.append(new_row_data)
            configprofileView.model().sourceModel().layoutChanged.emit()
            configprofileView.reset()
            break


    # Adjusted function to remove a profile
    def remove_profile(profile_id=None):
        if not profile_id:
            selected_index = configprofileView.selectionModel().currentIndex()
            if selected_index.isValid():
                profile_id = configprofileView.model().sourceModel()._data[selected_index.row()][2]
            else:
                QMessageBox.warning(None, "No Profile Selected", "Please select a profile to remove.")
                return

        profile_name = io_profile("read", profile_id, "profile", "name")

        if profile_name:
            confirm = QMessageBox.question(None, "Remove Profile", f"Are you sure you want to remove the profile '{profile_name}'? (Note this will not delete the folder from the cloud save location)", QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                io_profile("delete", profile_id)

                for row, data in enumerate(configprofileView.model().sourceModel()._data):
                    if data[2] == profile_id:
                        source_model = configprofileView.model().sourceModel()
                        source_model.beginRemoveRows(QModelIndex(), row, row)
                        source_model._data.pop(row)
                        source_model.endRemoveRows()
                        break
            else:
                return
        else:
            QMessageBox.warning(None, "Profile Not Found", f"The profile '{profile_id}' was not found in the configuration file.")


    # Function to open import profile dialog
    def import_profile_dialog():
        cloud_storage_path = io_global("read", "config", "cloud_storage_path")

        if not cloud_storage_path:
            QMessageBox.warning(None, "Cloud Storage Path Not Found", "Cloud storage path is not configured. Please configure it.")
            return

        if not os.path.exists(cloud_storage_path):
            return

        import_profile_dialog = uic.loadUi("import_profile.ui")
        import_profile_dialog.setWindowFlags(import_profile_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        import_profile_dialog.setFixedSize(import_profile_dialog.size())
        import_profile_dialog.importButton.setEnabled(False)

        center_dialog_over_dialog(dialog, import_profile_dialog)

        import_profile_dialog.listWidget.setEnabled(False)


        def validate_profile(profile_id):
            cloud_storage_path = io_global("read", "config", "cloud_storage_path")
            profile_info_path = os.path.join(cloud_storage_path, profile_id, "profile_info.savetitan")
            required_fields = ["name", "saves", "executable_name", "checkout"]

            existing_profile_id = io_profile("read", profile_id, "profile")
            if existing_profile_id != None:
                return 1

            try:
                profile_data = io_savetitan("read", profile_id, "profile")
                if not all(field in profile_data for field in required_fields):
                    with open("invalid_profiles.log", 'a') as f:
                        f.write(f"{profile_id}: Missing required fields\n")
                    return 2
                        
            except FileNotFoundError:
                with open("invalid_profiles.log", 'a') as f:
                    f.write(f"{profile_id}: Profile info not found\n")
                return 2

            return 0


        def scan_cloud_storage():
            cloud_storage_path = io_global("read", "config", "cloud_storage_path")
            invalid_profiles = 0

            import_profile_dialog.listWidget.clear()
            import_profile_dialog.listWidget.setEnabled(False)

            subfolders = [f.path for f in os.scandir(cloud_storage_path) if f.is_dir()]
            total_subfolders = len(subfolders)
            import_profile_dialog.progressBar.setMaximum(total_subfolders - 1)

            for i, subfolder in enumerate(subfolders):
                import_profile_dialog.progressBar.setValue(i)
                profile_id = os.path.basename(subfolder)

                validation_result = validate_profile(profile_id)
                if validation_result == 2:
                    invalid_profiles += 1
                    continue
                elif validation_result == 1:
                    continue
                elif validation_result == 0:
                    import_profile_dialog.listWidget.setEnabled(True)
                    profile_data = io_savetitan("read", profile_id, "profile")
                    item_text = f"{profile_data['name']} - {profile_data['executable_name']} ({profile_id})"
                    item = QtWidgets.QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, profile_id)
                    import_profile_dialog.listWidget.addItem(item)
                    continue

            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("Scan Completed")
            message = f"Scan completed.<br><br>" \
                    f"Profiles scanned: {total_subfolders}<br>"

            if invalid_profiles > 0:
                message += f"<br><font color='red'><b>Invalid profiles: {invalid_profiles}</b></font><br>"
                message += f"<font color='red'>(Logged to invalid_profiles.log)</font><br><br>"
            message += f"Profiles available for import: {import_profile_dialog.listWidget.count()}"
            message_box.setTextFormat(Qt.RichText)
            message_box.setText(message)
            center_dialog_over_dialog(import_profile_dialog, message_box)
            message_box.exec_()

            import_profile_dialog.progressBar.reset()
            import_profile_dialog.progressBar.setMaximum(100)


        # Function to import selected profile to profiles.ini
        def import_selected_profile():
            selected_item = import_profile_dialog.listWidget.currentItem()
            profile_id = selected_item.data(Qt.UserRole)

            profile_data = io_savetitan("read", profile_id, "profile")
            profile_name = profile_data["name"]
            saves = profile_data["saves"]
            sync_mode = profile_data["sync_mode"]
            executable_name = profile_data["executable_name"]

            cloud_storage_path = io_global("read", "config", "cloud_storage_path")

            if sys.platform == "win32":
                file_filter = "Executable Files (*.exe *.bat *.cmd)"
            elif sys.platform == "darwin":
                file_filter = "Executable Files (*.app *.command)"
            else:
                file_filter = "Executable Files (*.sh *.AppImage)"

            while True:
                executable_path, _ = QFileDialog.getOpenFileName(import_profile_dialog,
                                                                "Import Profile - Locate the executable for " + executable_name,
                                                                filter=file_filter)
                if not executable_path:
                    return
                elif executable_path.startswith(cloud_storage_path):
                    QMessageBox.warning(None, "Executable Location Error",
                                        "The selected executable is inside the cloud storage path. "
                                        "Please select an executable outside the cloud storage path.")
                else:
                    break

            selected_executable_name = os.path.basename(executable_path)
            if not selected_executable_name.lower() == executable_name.lower():
                message_box = QMessageBox()
                message_box.setIcon(QMessageBox.Warning)
                message_box.setWindowTitle("Executable Mismatch")
                message_box.setText("The selected executable does not match the expected executable name.")
                message_box.setInformativeText("Do you want to choose an executable again?")
                message_box.addButton("Choose Again", QMessageBox.YesRole)
                message_box.addButton("Continue Import", QMessageBox.NoRole)
                message_box.setDefaultButton(QMessageBox.Yes)
                response = message_box.exec_()
                if response == 0:
                    executable_path, _ = QFileDialog.getOpenFileName(import_profile_dialog,
                                                                    "Import Profile - Locate the executable for " + executable_name,
                                                                    filter=file_filter)
                    if not executable_path:
                        return
                    selected_executable_name = os.path.basename(executable_path)
                    if not selected_executable_name.lower() == executable_name.lower():
                        QMessageBox.warning(None, "Executable Mismatch",
                                            "The selected executable still does not match the expected executable name. "
                                            "Profile import cancelled.")
                        return

            while True:
                local_save_folder = QFileDialog.getExistingDirectory(import_profile_dialog,
                                                                    "Import Profile - Locate the save folder for " + profile_name,
                                                                    options=QFileDialog.ShowDirsOnly)
                if not local_save_folder:
                    return
                elif local_save_folder.startswith(cloud_storage_path):
                    QMessageBox.warning(None, "Save Location Error",
                                        "The selected save folder is inside the cloud storage path. "
                                        "Please select a save folder outside the cloud storage path.")
                else:
                    break

            io_profile("write", profile_id, "profile", "name", profile_name)
            io_profile("write", profile_id, "profile", "local_save_folder", local_save_folder)
            io_profile("write", profile_id, "profile", "game_executable", executable_path)
            io_profile("write", profile_id, "profile", "saves", saves)
            io_profile("write", profile_id, "profile", "sync_mode", sync_mode)
            io_profile("write", profile_id, "profile", "executable_name", executable_name)
            io_profile("write", profile_id, "profile", "executable_path", executable_path)

            QMessageBox.information(None, "Success", "Profile imported successfully.")
            new_row_data = [profile_name, sync_mode, profile_id]
            configprofileView.model().sourceModel()._data.append(new_row_data)

            configprofileView.model().sourceModel().layoutChanged.emit()

            configprofileView.reset()

            import_profile_dialog.close()


        import_profile_dialog.scanButton.clicked.connect(scan_cloud_storage)
        import_profile_dialog.importButton.clicked.connect(import_selected_profile)
        import_profile_dialog.closeButton.clicked.connect(import_profile_dialog.close)
        import_profile_dialog.listWidget.currentItemChanged.connect(lambda: import_profile_dialog.importButton.setEnabled(True if import_profile_dialog.listWidget.currentItem() else False))

        import_profile_dialog.exec_()
       
       
    # Show the about dialog window
    def about_dialog(config_dialog):
        about = QMessageBox()
        about.setWindowIcon(QIcon('icon/path'))
        about.setWindowTitle("About SaveTitan")
        about.setTextFormat(Qt.RichText)

        about_text = """
        <span style="font-weight:600; font-family:Arial; color:#555;">SaveTitan v0.10</span>
        <p>
        SaveTitan is a powerful game save management tool that allows you to sync your game saves between local storage and cloud storage. 
        It is designed for granularity and control so you get the best experience jumping from device to device.
        </p>
        <p>
        By Sean Bowman
        </p>
        <p><span style="font-size:10px;"><a href="https://www.flaticon.com/free-icons/storage style="color:#36AE7C;" title="storage icons">Storage icons created by Hilmy Abiyyu A. - Flaticon</a></span></p>
        """
        about.setText(about_text)
        center_dialog_over_dialog(config_dialog, about)

        about.exec_()


    # Update the executable location for selected profile
    def update_executable():
        cloud_storage_path = io_global("read", "config", "cloud_storage_path")

        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        profile_name = io_profile("read", profile_id, "profile", "name")
        if not profile_name:
            QMessageBox.warning(None, "Profile Not Found", "The selected profile was not found in the config file.")
            return

        if sys.platform == "win32":
            file_filter = "Executable Files (*.exe *.bat *.cmd)"
        elif sys.platform == "darwin":
            file_filter = "Executable Files (*.app *.command)"
        else:
            file_filter = "Executable Files (*.sh *.AppImage)"

        while True:
            filepath, _ = QFileDialog.getOpenFileName(None, f"Edit Profile - Locate the executable for {profile_name}", filter=file_filter)

            if not filepath:
                return

            if filepath.startswith(cloud_storage_path):
                QMessageBox.warning(None, "Executable Location Error",
                                    "The selected executable is inside the cloud storage path. "
                                    "Please select an executable outside the cloud storage path.")
            else:
                break

        dialog.executableField.setText(filepath)


    # Update save game location for selected profile
    def update_local_save_folder():
        cloud_storage_path = io_global("read", "config", "cloud_storage_path")

        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        profile_name = io_profile("read", profile_id, "profile", "name")
        if not profile_name:
            QMessageBox.warning(None, "Profile Not Found", "The selected profile was not found in the config file.")
            return

        while True:
            save_folder = QFileDialog.getExistingDirectory(None, f"Edit Profile - Locate the save folder for {profile_name}", options=QFileDialog.ShowDirsOnly)

            if not save_folder:
                return

            if save_folder.startswith(cloud_storage_path):
                QMessageBox.warning(None, "Save Location Error",
                                    "The selected save folder is inside the cloud storage path. "
                                    "Please select a save folder outside the cloud storage path.")
            else:
                break

        dialog.saveField.setText(save_folder)


    # Function to update fields in the edit profile section with selected profile
    def update_fields(index):
        if index.isValid():
            row_data = configprofileView.model().sourceModel()._data[index.row()]
            profile_id = row_data[2]
            try:
                profile_data = io_profile("read", profile_id, "profile")
                profile_fields = profile_data
                name = profile_fields.get("name")
                game_executable = profile_fields.get("game_executable")
                local_save_folder = profile_fields.get("local_save_folder")
                save_slot = profile_fields.get("save_slot")
                sync_mode = profile_fields.get("sync_mode", "Sync")
            except Exception as e:
                return

            try:
                dialog.profilenameField.setText(name)
                dialog.executableField.setText(game_executable)
                dialog.saveField.setText(local_save_folder)
                dialog.syncenableRadio.setChecked(sync_mode == "Sync")
                dialog.syncdisableRadio.setChecked(sync_mode != "Sync")
            except Exception as e:
                return


    # Function to save field information to selected profile
    def save_profile_fields():
        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to save the fields.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        profile_data = io_profile("read", profile_id, "profile")
        if profile_data is None:
            QMessageBox.warning(None, "Profile Not Found", "The selected profile does not exist.")
            return

        profile_name = dialog.profilenameField.text()
        local_save_folder = dialog.saveField.text()
        game_executable = dialog.executableField.text()
        sync_mode = "Sync" if dialog.syncenableRadio.isChecked() else ""

        profiles_data = io_profile("read", None, "profile")
        for section in profiles_data:
            if section != profile_id and profiles_data[section]['name'].lower() == profile_name.lower():
                QMessageBox.critical(None, "Profile Already Exists",
                                    "A profile with the same name already exists. Please choose a different name.")
                return

        io_profile("write", profile_id, "profile", "name", profile_name)
        io_profile("write", profile_id, "profile", "local_save_folder", local_save_folder)
        io_profile("write", profile_id, "profile", "game_executable", game_executable)
        io_profile("write", profile_id, "profile", "sync_mode", sync_mode)

        save_slot = io_savetitan("read", profile_id, "saves", "save_slot")
        io_savetitan("write", profile_id, "profile", "name", profile_name)
        io_savetitan("write", profile_id, "profile", "executable_name", os.path.basename(game_executable))

        configprofileView.model().sourceModel()._data = load_data_into_model_data()

        for i in range(configprofileView.model().rowCount(QtCore.QModelIndex())):
            if configprofileView.model().sourceModel()._data[i][2] == profile_id:
                new_index = configprofileView.model().index(i, 0)
                configprofileView.setCurrentIndex(new_index)
                update_fields(new_index)
                break

        QMessageBox.information(None, "Profile Saved", "The profile has been successfully saved.")


    # Connections for button clicks
    dialog.executablefieldButton.clicked.connect(update_executable)
    dialog.savefieldButton.clicked.connect(update_local_save_folder)
    dialog.addButton.clicked.connect(add_profile)
    dialog.removeButton.clicked.connect(remove_profile)
    dialog.importButton.clicked.connect(import_profile_dialog)
    dialog.settingsButton.clicked.connect(global_settings_dialog)
    dialog.applyButton.clicked.connect(save_profile_fields)


    # Function to open a local save location in file explorer
    def open_local_save_location(profile_id):
        local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
        QDesktopServices.openUrl(QUrl.fromLocalFile(local_save_folder))


    # Function to open a cloud storage location in file explorer
    def open_cloud_location_storage(profile_id):
        cloud_storage_path = io_global("read", "config", "cloud_storage_path")
        folder_path = os.path.join(cloud_storage_path, profile_id)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))


    # Function to create context menu
    def context_menu(point):
        menu = QMenu()

        open_cloud_storage_action = QAction("Open Cloud Storage", menu)
        open_local_save_action = QAction("Open Local Save", menu)
        delete_profile_action = QAction("Delete Profile", menu)
        open_save_mgmt_action = QAction("Open Save Manager", menu)
        open_save_editor_action = QAction("Open Config Editor", menu)
        copy_profile_id_action = QAction("Copy Profile ID", menu)

        index = configprofileView.indexAt(point)
        
        if index.isValid():
            selected_profile_id = configprofileView.model().sourceModel()._data[index.row()][2]

            open_cloud_storage_action.triggered.connect(lambda: open_cloud_location_storage(selected_profile_id))
            open_local_save_action.triggered.connect(lambda: open_local_save_location(selected_profile_id))
            delete_profile_action.triggered.connect(lambda: remove_profile(selected_profile_id))
            open_save_mgmt_action.triggered.connect(lambda: save_mgmt_dialog(selected_profile_id))
            open_save_editor_action.triggered.connect(lambda: ConfigEditorDialog(selected_profile_id).exec_())
            copy_profile_id_action.triggered.connect(lambda: QApplication.clipboard().setText(selected_profile_id))

            menu.addAction(open_local_save_action)
            menu.addAction(open_cloud_storage_action)
            menu.addSeparator()
            menu.addAction(open_save_mgmt_action)
            menu.addAction(open_save_editor_action)
            menu.addSeparator()
            menu.addAction(delete_profile_action)
            menu.addSeparator()
            menu.addAction(copy_profile_id_action)

            menu.exec_(configprofileView.viewport().mapToGlobal(point))


    class ConfigEditorDialog(QDialog):
        def __init__(self, profile_id, parent=None):
            super().__init__(parent)

            self.ui = uic.loadUi("config_editor.ui", self)
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
            self.setFixedSize(self.size())
            
            #self.ui.editor_tableView.setEnabled(False)

            self.profile_id = profile_id
            
            self.file_formats = {}

            self.file_combo_box = self.ui.file_comboBox
            self.section_combo_box = self.ui.section_comboBox
            self.filter_edit_box = self.ui.filter_lineEdit
            self.editor_table_view = self.ui.editor_tableView

            self.apply_button = self.ui.apply_pushButton
            self.okay_button = self.ui.okay_pushButton
            self.reset_button = self.ui.reset_pushButton

            self.apply_button.clicked.connect(self.save_changes)
            self.okay_button.clicked.connect(self.save_changes_and_close)

            self.populate_file_combo_box()

            self.table_model = QStandardItemModel()
            self.editor_table_view.setModel(self.table_model)

            self.editor_table_view.verticalHeader().setVisible(False)

            self.file_combo_box.currentIndexChanged.connect(self.populate_section_combo_box)
            self.section_combo_box.currentIndexChanged.connect(self.populate_table_view)

            self.populate_table_view()

        def populate_file_combo_box(self):
            profile_data = io_profile("read", self.profile_id, "profile")
            local_save_folder = io_profile("read", self.profile_id, "profile", "local_save_folder")

            file_paths = []
            for root, dirs, files in os.walk(local_save_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    _, ext = os.path.splitext(file_path)
                    if ext.lower() == '.ini':
                        with open(file_path, 'r') as f:
                            first_line = f.readline().strip()
                            if re.match('\[.*\]', first_line):
                                file_paths.append(file_path)
                                self.file_formats[file_path] = '.ini'
                    elif ext.lower() == '.json':
                        file_paths.append(file_path)
                        self.file_formats[file_path] = '.json'

            self.file_combo_box.clear()
            self.file_combo_box.addItems(["Files"] + file_paths)


        def flatten_json(self, y):
            out = {}

            def flatten(x, name=''):
                if type(x) is dict:
                    for a in x:
                        flatten(x[a], name + a + '/')
                elif type(x) is list:
                    i = 0
                    for a in x:
                        flatten(a, name + str(i) + '/')
                        i += 1
                else:
                    out[name[:-1]] = x

            flatten(y)
            return out

            self.file_combo_box.clear()
            self.file_combo_box.addItems(["Files"] + file_paths)
            
            
        def populate_section_combo_box(self):
            file_path = self.file_combo_box.currentText()

            if file_path == "Files":
                return

            self.section_combo_box.clear()

            if self.file_formats[file_path] == '.ini':
                config = configparser.ConfigParser()
                config.read(file_path)

                self.section_combo_box.addItems(config.sections())
                
            elif self.file_formats[file_path] == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    sections = set(key.rsplit('/', 1)[0] for key in self.flatten_json(data).keys())
                    self.section_combo_box.addItems(list(sections))
        
        
        def populate_table_view(self):
            file_path = self.file_combo_box.currentText()
            section = self.section_combo_box.currentText()

            if file_path == "Files":
                return

            self.table_model.clear()

            self.table_model.setHorizontalHeaderLabels(["Field", "Value"])

            self.editor_table_view.resizeRowsToContents()

            file_format = self.file_formats.get(file_path)

            if file_format == '.ini':
                config = configparser.ConfigParser()
                config.read(file_path)

                if section in config:
                    self.ui.editor_tableView.setEnabled(True)
                    for key, value in config.items(section):
                        self.add_row_to_table(key, value)
                        self.editor_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
                        self.editor_table_view.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)

            elif file_format == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    flattened_data = self.flatten_json(data)

                    section += '/'

                    for key in flattened_data:
                        if key.startswith(section):
                            self.ui.editor_tableView.setEnabled(True)
                            modified_key = key.replace(section, '')
                            value = flattened_data[key]
                            if '/' not in modified_key:
                                self.add_row_to_table(modified_key, str(value))

                    stripped_section = section.strip('/')
                    if stripped_section in data and not isinstance(data[stripped_section], (dict, list)):
                        self.add_row_to_table("Value", str(data[stripped_section]))

            self.editor_table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
            self.editor_table_view.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)


        def add_row_to_table(self, key, value):
            if isinstance(value, list):
                value = ', '.join(map(str, value))

            key_item = QStandardItem(key)
            value_item = QStandardItem(value)

            key_item.setEditable(False)

            self.table_model.appendRow([key_item, value_item])


        def save_changes(self):
            file_path = self.file_combo_box.currentText()

            cloud_storage_path = io_global("read", "config", "cloud_storage_path")
            backup_folder_path = os.path.join(cloud_storage_path, str(self.profile_id), "config_backup")

            hostname = socket.gethostname()

            path_parts = os.path.normpath(file_path).split(os.sep)

            necessary_part_path = os.path.join(*(hostname, path_parts[0].replace(':', ''), *path_parts[1:]))

            backup_file_path = os.path.join(backup_folder_path, necessary_part_path)

            os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)

            if not os.path.exists(backup_file_path):
                shutil.copy2(file_path, backup_file_path)

            file_format = self.file_formats.get(file_path)
            if file_format == '.ini':
                config = configparser.ConfigParser()
                for row in range(self.table_model.rowCount()):
                    key = self.table_model.item(row, 0).text()
                    value = self.table_model.item(row, 1).text()
                    config.set('DEFAULT', key, value)

                with open(file_path, 'w') as file:
                    config.write(file)

            elif file_format == '.json':
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    flattened_data = self.flatten_json(data)
                    section = self.section_combo_box.currentText() + '/'
                    for row in range(self.table_model.rowCount()):
                        key = self.table_model.item(row, 0).text()
                        value = self.table_model.item(row, 1).text()
                        complete_key = section + key
                        if complete_key in flattened_data:
                            keys = complete_key.split('/')
                            sub_data = data
                            for sub_key in keys[:-1]:
                                sub_data = sub_data[sub_key]
                            sub_data[keys[-1]] = value

                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=4)
                    
            msgBox = QMessageBox()
            msgBox.setWindowTitle("Config File Saved")
            msgBox.setText(f"The configuration file has been saved successfully.\n\nA backup of the original file has been stored at:\n{backup_file_path}")
            msgBox.exec_()

        def save_changes_and_close(self):
            self.save_changes()
            self.accept()
            
        
    configprofileView.setContextMenuPolicy(Qt.CustomContextMenu)
    configprofileView.customContextMenuRequested.connect(context_menu)
    
    configprofileView.selectionModel().currentChanged.connect(update_fields)

    dialog.actionNew_Profile.triggered.connect(add_profile)
    dialog.actionExit.triggered.connect(dialog.close)
    dialog.actionAbout.triggered.connect(lambda: about_dialog(dialog))

    dialog.show()        


# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-runprofile", help="Specify the game profile to be used")
parser.add_argument("-runid", help="Specify the profile ID to be used")
parser.add_argument("-list", action='store_true', help="List all profiles in profiles.ini")
args = parser.parse_args()

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

app = QApplication([])
profile_data = None

cloud_storage_path = io_global("read", "config", "cloud_storage_path")

if args.list:
    profile_fields = io_profile("read", None, "profile")
    if profile_fields is None:
        print("No profiles found in profiles.ini")
        sys.exit(1)
    else:
        for profile_id, profile_data in profile_fields.items():
            name = profile_data.get('name')
            save_slot = profile_data.get('save_slot')
            print(f"{profile_id} - {name} - Save Slot: {save_slot}")
        sys.exit(1)
elif args.runprofile:

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
    
    check_and_sync_saves(profile_id)
    
elif args.runid:
    if not cloud_storage_path:
        print("Cloud storage path is not configured. Run the script without a parameter to run the first-time setup")
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

    #Profile validity code to go here]

    check_and_sync_saves(profile_id)
else:
    show_config_dialog()
    
app.exec_()