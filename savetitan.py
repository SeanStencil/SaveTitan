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


from datetime import datetime, timedelta
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QInputDialog, QMenu, QAction, QDialog, QListWidgetItem
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QTimer, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QUrl


# REFACTORED FUNCTION (DONE): Get the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))


# REFACTORED FUNCTION (DONE): Define the config file path
profiles_config_file = os.path.join(script_dir, "profiles.ini")
global_config_file = os.path.join(script_dir, "global.ini")


# Generate a 16 character string for use for profile_id's
def generate_id():
    characters = string.ascii_letters + string.digits
    id_length = 16
    random_id = ''.join(random.choices(characters, k=id_length))
    return random_id


# REFACTORED FUNCTION (DONE): Check a function's ability to perform the given action (read, write, execute) on the file/folder path
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


# REFACTORED FUNCTION (DONE): Try and wake up the network location
def network_share_accessible():
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

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
        

# REFACTORED FUNCTION: Function to read and write the profiles.ini and global.ini files
def io_config_file(config_type, read_write_mode, profile_id=None, field=None, write_value=None):
    config = configparser.ConfigParser()
    if config_type == "profiles_file":
        config_file = profiles_config_file
        config_section = profile_id
    elif config_type == "global_file":
        config_file = global_config_file
        config_section = "Global Settings"
    else:
        raise ValueError("Invalid config_type. Expected 'profiles_file' or 'global_file'.")

    if not check_permissions(config_file, config_type, "read"):
        raise PermissionError(f"Permission denied to read the {config_type}.")

    config.read(config_file)

    if config_type == "profiles_file" and read_write_mode == "read" and profile_id and not config.has_section(profile_id):
            print("No section found for provided profile_id, returning None")
            return None

    if read_write_mode == "read":
        if not field:
            return {s: dict(config.items(s)) for s in config.sections()}
        else:
            if field.lower() == "name" and write_value:
                for section in config.sections():
                    if config.has_option(section, field) and config.get(section, field).lower() == write_value.lower():
                        return section
                return None
            else:
                return config.get(config_section, field) if config.has_option(config_section, field) else None

    elif read_write_mode == "write":
        if not check_permissions(config_file, config_type, "write"):
            raise PermissionError(f"Permission denied to write to the {config_type}.")

        if not field:
            raise ValueError("Field must be specified in 'write' mode.")

        if not config.has_section(config_section):
            config.add_section(config_section)

        config.set(config_section, field, write_value or "")
        with open(config_file, "w") as file:
            config.write(file)

    elif read_write_mode == "delete":
        if config_type != "profiles_file":
            raise ValueError("The 'delete' mode can only be used when config_type is 'profiles_file'.")

        if not check_permissions(config_file, config_type, "write"):
            raise PermissionError(f"Permission denied to delete from the {config_type}.")

        if not profile_id:
            raise ValueError("Profile ID must be specified in 'delete' mode.")

        if config.has_section(profile_id):
            config.remove_section(profile_id)
            with open(config_file, "w") as file:
                config.write(file)
        else:
            raise ValueError(f"No section found with Profile ID: {profile_id}")

    else:
        raise ValueError("Invalid read_write_mode. Expected 'read', 'write', or 'delete'.")


# REFACTORED FUNCTION (DONE): Function to read and write the profile_info.savetitan file in the cloud storage location
def io_savetitan_file(read_write_mode, profile_id, field, write_value=None):
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    profile_info_path = os.path.join(cloud_storage_path, f"{profile_id}", "profile_info.savetitan")
    if not check_permissions(profile_info_path, 'file', 'read'):
        raise PermissionError(f"Permission denied to read the profile file at {profile_info_path}")

    config = configparser.ConfigParser()
    config.read(profile_info_path)

    if read_write_mode == "read":
        return config.get(profile_id, field) if config.has_option(profile_id, field) else None
    elif read_write_mode == "write":
        if not field:
            raise ValueError("Field must be specified in 'write' mode.")
        if not check_permissions(profile_info_path, 'file', 'write'):
            raise PermissionError(f"Permission denied to write to the profile file at {profile_info_path}")
        config.set(profile_id, field, write_value or "")
        with open(profile_info_path, "w") as file:
            config.write(file)
    else:
        raise ValueError("Invalid read_write_mode. Expected 'read' or 'write'.")


# REFACTORED FUNCTION (DONE): Checks for file mismatch
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


# REFACTORED FUNCTION (DONE): Function to sync saves (Copy local saves to cloud storage)
def sync_save_cloud(profile_id):
    local_save_folder = io_config_file("profiles_file", "read", profile_id, "local_save_folder")
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    save_slot = io_config_file("profiles_file", "read", profile_id, "save_slot")

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


# REFACTORED FUNCTION (DONE): Function to sync saves (Copy cloud saves to local storage)
def sync_save_local(profile_id):
    local_save_folder = io_config_file("profiles_file", "read", profile_id, "local_save_folder")
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    save_slot = io_config_file("profiles_file", "read", profile_id, "save_slot")
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


# REFACTORED FUNCTION (DONE): Perform backup function prior to sync
def make_backup_copy(profile_id, which_side):
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    save_slot = io_config_file("profiles_file", "read", profile_id, "save_slot")
    cloud_profile_folder_save = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)
    cloud_profile_folder_save_bak = cloud_profile_folder_save + ".bak"

    if which_side not in ["local_backup", "cloud_backup"]:
        raise Exception("Invalid which_side argument")

    os.makedirs(cloud_profile_folder_save_bak, exist_ok=True)

    if which_side == "local_backup":
        local_save_folder = io_config_file("profiles_file", "read", profile_id, "local_save_folder")
        
        if os.path.exists(cloud_profile_folder_save_bak):
            shutil.rmtree(cloud_profile_folder_save_bak)

        shutil.copytree(local_save_folder, cloud_profile_folder_save_bak)

    elif which_side == "cloud_backup":
        if os.path.exists(cloud_profile_folder_save_bak):
            shutil.rmtree(cloud_profile_folder_save_bak)

        shutil.copytree(cloud_profile_folder_save, cloud_profile_folder_save_bak)


# Export a .savetitan file for the profile folder in cloud storage
def export_profile_info(profile_name, save_slot, saves, profile_id, sync_mode, executable_name):
    global cloud_storage_path

    if not network_share_accessible():
        QMessageBox.critical(None, "Add Profile Aborted",
                             "The network location is not accessible, the process to add the profile has been aborted.")
        return

    folder_path = os.path.join(cloud_storage_path, profile_id)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, "profile_info.savetitan")
    config = configparser.ConfigParser()
    config[profile_id] = {
        "name": profile_name,
        "save_slot": str(save_slot),
        "saves": str(saves),
        "sync_mode": sync_mode,
        "executable_name": executable_name,
        "checkout": ""
    }

    config["saves"] = {
        "save1": "Save 1"
    }

    config.remove_option(profile_id, "profile_id")

    try:
        with open(file_path, "w") as file:
            config.write(file)
    except Exception as e:
        QMessageBox.critical(None, "Add Profile Aborted",
                             f"Error exporting profile info: {str(e)}. The process to add the profile has been aborted.")


# REFACTORED FUNCTION (DONE): Function to check and sync saves
def check_and_sync_saves(profile_id):

    #Load data set
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    cloud_profile_folder = os.path.join(cloud_storage_path, f"{profile_id}")
    profile_data = io_config_file("profiles_file", "read", profile_id)
    profile_fields = profile_data[profile_id]
    name = profile_fields.get("name")
    game_executable = profile_fields.get("game_executable")
    local_save_folder = profile_fields.get("local_save_folder")
    save_slot = profile_fields.get("save_slot")
    sync_mode = profile_fields.get("sync_mode")
    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)
    profile_info_savetitan_path = os.path.join(cloud_storage_path, profile_id + "profile_into.savetitan")

    # Check: Checkout Hostname
    checkout_previous_user = io_savetitan_file("read", profile_id, "checkout")
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
            io_savetitan_file("write", profile_id, "checkout", checkout_current_user)

    elif not checkout_previous_user:
        io_savetitan_file("write", profile_id, "checkout", checkout_current_user)

    # Check: If files with the same name are identical
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

            config_profiles = configparser.ConfigParser()
            config_profiles.read('profiles.ini')
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
                io_savetitan_file("write", profile_id, "checkout", None)
                sync_diag.accept()
            
            def on_rejected_connect():
                io_savetitan_file("write", profile_id, "checkout", None)
                sys.exit()

            sync_diag.downloadButton.clicked.connect(lambda: [sync_save_local(profile_id), launch_game(profile_id), sync_diag.accept()])
            sync_diag.uploadButton.clicked.connect(lambda: [launch_game(profile_id), sync_diag.accept()])
            sync_diag.nosyncButton.clicked.connect(lambda: [on_nosyncButton_clicked()])

            sync_diag.rejected.connect(lambda: on_rejected_connect())
            
            sync_diag.exec_()
    else:
        launch_game(profile_id)


# REFACTORED FUNCTION (DONE): Function to launch the game
def launch_game(profile_id):
    game_executable = io_config_file("profiles_file", "read", profile_id, "game_executable")
    profile_info_savetitan_path = os.path.join(cloud_storage_path, profile_id + "profile_into.savetitan")
    
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

        io_savetitan_file("write", profile_id, "checkout", None)

    QTimer.singleShot(0, launch_game_dialog)


# REFACTORED FUNCTION (DONE): Function to launch the game without sync
def launch_game_without_sync(game_executable):
    game_executable = io_config_file("profiles_file", "read", profile_id, "game_executable")
    profile_info_savetitan_path = os.path.join(cloud_storage_path, profile_id + "profile_into.savetitan")
    
    if not check_permissions(game_executable, 'game executable', "execute"):
        return

    subprocess.Popen(game_executable)
    
    sys.exit()


# Function to set the cloud storage location
def set_cloud_storage_path():
    current_cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path") or ""
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

        io_config_file("global_file", "write", None, "cloud_storage_path", cloud_storage_path)
        break

    dialog.addButton.setEnabled(True)
    dialog.importButton.setEnabled(True)


# REFACTORED FUNCTION: Calculate the center position over another dialog window
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

    # Get the DPI scaling factor
    app = QApplication.instance()
    screen = app.screens()[0]
    dpiScaling = screen.logicalDotsPerInch() / 96.0

    # Adjust the size of the dialog based on the DPI scaling factor
    width = int(dialog.width() * dpiScaling)
    height = int(dialog.height() * dpiScaling)
    dialog.setFixedSize(width, height)

    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
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
        profiles_config = configparser.ConfigParser()
        profiles_config.read(profiles_config_file)

        data = []
        for section in profiles_config.sections():
            profile = profiles_config[section]
            name = profile.get("name")
            sync_mode = profile.get("sync_mode")

            row = [name, sync_mode, section]

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
    def save_mgmt_dialog(selected_profile_id):
        save_mgmt_dialog = uic.loadUi("save_mgmt.ui")
        save_mgmt_dialog.setWindowFlags(save_mgmt_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        save_mgmt_dialog.setFixedSize(save_mgmt_dialog.size())

        config = configparser.ConfigParser()
        config.read(profiles_config_file)
        if selected_profile_id not in config.sections():
            QMessageBox.warning(None, "Profile Not Found", "The selected profile does not exist.")
            return

        profile_info_config = configparser.ConfigParser()
        profile_folder = os.path.join(cloud_storage_path, selected_profile_id)
        profile_info_file_path = os.path.join(profile_folder, "profile_info.savetitan")

        profile_info_config.read(profile_info_file_path)

        save_mgmt_dialog.profilenameField.setText(profile_info_config.get(selected_profile_id, 'name'))
        save_mgmt_dialog.saveField.setText(config.get(selected_profile_id, 'local_save_folder'))

        save_slot = config.get(selected_profile_id, 'save_slot')
        save_slot_key = f"save{save_slot}"

        if 'saves' in profile_info_config.sections() and save_slot_key in profile_info_config['saves']:
            save_mgmt_dialog.saveslotField.setText(profile_info_config.get('saves', save_slot_key))

        center_dialog_over_dialog(QApplication.activeWindow(), save_mgmt_dialog)

        if 'saves' in profile_info_config.sections():
            saves_data = dict(profile_info_config['saves'])
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

            number_of_saves = int(profile_info_config.get(selected_profile_id, "saves", fallback="0")) + 1
            profile_info_config.set(selected_profile_id, "saves", str(number_of_saves))

            with open(profile_info_file_path, "w") as file:
                profile_info_config.write(file)

            new_save_name = f"Save {number_of_saves}"
            profile_info_config.set('saves', f'save{number_of_saves}', new_save_name)
                
            with open(profile_info_file_path, "w") as file:
                profile_info_config.write(file)

            new_save_folder = os.path.join(cloud_storage_path, selected_profile_id, f'save{number_of_saves}')
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

            if selected_save_key == f"save{config.get(selected_profile_id, 'save_slot')}":
                return

            current_save_slot = config.get(selected_profile_id, 'save_slot')
            local_save_folder = config.get(selected_profile_id, 'local_save_folder')

            cloud_save_folder = os.path.join(cloud_storage_path, selected_profile_id, f"save{current_save_slot}")

            reply = QMessageBox.question(None, "Upload current save?",
                                         "Do you want to upload your current save before switching? Your local save will be replaced with the selected one.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                sync_save_cloud_workaround(local_save_folder, cloud_save_folder)

            new_save_slot = selected_save_key.replace('save', '')
            config.set(selected_profile_id, 'save_slot', new_save_slot)
            with open(profiles_config_file, "w") as file:
                config.write(file)

            profile_info_file_path = os.path.join(cloud_storage_path, selected_profile_id, "profile_info.savetitan")
            profile_info_config = configparser.ConfigParser()
            profile_info_config.read(profile_info_file_path)
            profile_info_config.set(selected_profile_id, 'save_slot', new_save_slot)
            with open(profile_info_file_path, "w") as file:
                profile_info_config.write(file)

            save_mgmt_dialog.saveslotField.setText(selected_item.text())

            new_cloud_save_folder = os.path.join(cloud_storage_path, selected_profile_id, selected_save_key)
            sync_save_local(new_cloud_save_folder, local_save_folder, new_cloud_save_folder)

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

            profile_info_config.remove_option('saves', selected_save_key)

            with open(profile_info_file_path, "w") as file:
                profile_info_config.write(file)

            shutil.rmtree(os.path.join(cloud_storage_path, selected_profile_id, selected_save_key))

            list_item = save_mgmt_dialog.save_listWidget.takeItem(save_mgmt_dialog.save_listWidget.row(selected_item))
            del list_item
                

        def handle_rename_save_button():
            selected_items = save_mgmt_dialog.save_listWidget.selectedItems()
            if not selected_items:
                return

            selected_item = selected_items[0]
            selected_save_field = selected_item.data(Qt.UserRole)

            new_save_name, ok = QInputDialog.getText(save_mgmt_dialog, "Rename Save", "Enter new save name:")
            if not ok or not new_save_name:
                return

            # Check if the new save name already exists
            existing_save_names = [profile_info_config.get('saves', key).lower() for key in profile_info_config.options('saves')]
            if new_save_name.lower() in existing_save_names:
                QMessageBox.warning(None, "Name Already Exists", "A save with this name already exists. Please choose a different name.")
                return

            profile_info_config.set('saves', selected_save_field, new_save_name)

            with open(profile_info_file_path, "w") as file:
                profile_info_config.write(file)

            selected_item.setText(new_save_name)

        save_mgmt_dialog.newsaveButton.clicked.connect(handle_new_save_button)
        save_mgmt_dialog.loadsaveButton.clicked.connect(handle_load_save_button)
        save_mgmt_dialog.renamesaveButton.clicked.connect(handle_rename_save_button)
        save_mgmt_dialog.deletesaveButton.clicked.connect(handle_delete_save_button)

        save_mgmt_dialog.exec_()


    # Function to add a profile
    def add_profile():
        cloud_storage_path = io_config_file("global_file", "read", "Global Settings", "cloud_storage_path")
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

            if io_config_file("profiles_file", "read", None, "name", profile_name) != None:
                QMessageBox.critical(None, "Profile Already Exists", "A profile with the same name already exists. Please choose a different name.")
                continue

            sync_mode = "Sync" if add_profile_dialog.syncRadio.isChecked() else "Backup"

            profile_id = None
            while True:
                profile_id = generate_id()
                if not io_config_file("profiles_file", "read", profile_id):
                    break

            save_slot = 1
            saves = 1

            profile_folder = os.path.join(cloud_storage_path, profile_id)
            os.makedirs(profile_folder, exist_ok=True)

            try:
                export_profile_info(profile_name, save_slot, saves, profile_id, sync_mode, os.path.basename(game_executable))

                profile_fields = {
                    "name": profile_name,
                    "local_save_folder": local_save_folder,
                    "game_executable": game_executable,
                    "save_slot": str(save_slot),
                    "saves": str(saves),
                    "sync_mode": sync_mode,
                }

                for field, value in profile_fields.items():
                    io_config_file("profiles_file", "write", profile_id, field, value)

                new_row_data = [profile_name, sync_mode, profile_id]
                configprofileView.model().sourceModel()._data.append(new_row_data)
                configprofileView.model().sourceModel().layoutChanged.emit()
                configprofileView.reset()
                break

            except Exception as e:
                QMessageBox.warning(None, "Profile Creation Error", "There was an error creating the profile. The operation has been aborted.", QMessageBox.Ok)


    # Adjusted function to remove a profile
    def remove_profile(profile_id=None):
        if not profile_id:
            selected_index = configprofileView.selectionModel().currentIndex()
            if selected_index.isValid():
                profile_id = configprofileView.model().sourceModel()._data[selected_index.row()][2]
            else:
                QMessageBox.warning(None, "No Profile Selected", "Please select a profile to remove.")
                return

        profile_name = io_config_file("profiles_file", "read", profile_id, "name")

        if profile_name:
            confirm = QMessageBox.question(None, "Remove Profile", f"Are you sure you want to remove the profile '{profile_name}'? (Note this will not delete the folder from the cloud save location)", QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                io_config_file("profiles_file", "delete", profile_id)

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
        cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

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


        # Function to write invalid profiles to log file
        def write_to_log(filepath, subfolder, message):
            with open(filepath, 'a') as f:
                f.write(f"{subfolder}: {message}\n")


        # REFACTORED FUNCTION: Scan the cloud storage location for importable profiles
        def scan_cloud_storage():
            scanned_count = 0
            added_count = 0
            invalid_count = 0
            can_import_count = 0
            
            import_profile_dialog.progressBar.setValue(0)
            import_profile_dialog.listWidget.clear()

            cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
            if not cloud_storage_path:
                return

            if not network_share_accessible():
                QMessageBox.critical(None, "Network Error", 
                                     "An error occurred while trying to access the network share. Please check your connection and try again.")
                return

            config = configparser.ConfigParser()
            config.read(profiles_config_file)

            subfolders = [f.path for f in os.scandir(cloud_storage_path) if f.is_dir()]
            invalid_profiles_path = os.path.join(script_dir, "invalid_profiles.log")
            open(invalid_profiles_path, 'w').close()

            total_subfolders = len(subfolders)
            import_profile_dialog.progressBar.setMaximum(total_subfolders - 1)

            for subfolder in subfolders:
                profile_info_file_path = os.path.join(subfolder, "profile_info.savetitan")
                import_profile_dialog.progressBar.setValue(import_profile_dialog.progressBar.value() + 1)
                if not os.path.exists(profile_info_file_path):
                    write_to_log(invalid_profiles_path, subfolder, "Profile info not found")
                    invalid_count += 1
                    scanned_count += 1
                    continue

                config_savetitan = configparser.ConfigParser()
                config_savetitan.read(profile_info_file_path)

                if not config_savetitan.sections():
                    write_to_log(invalid_profiles_path, subfolder, "Config sections not found")
                    invalid_count += 1
                    scanned_count += 1
                    continue

                profile_id = config_savetitan.sections()[0]
                #required_fields = ['name', 'save_slot', 'saves', 'sync_mode', 'executable_name']
                #if not all(config_savetitan.has_option(profile_id, field) for field in required_fields):
                #    write_to_log(invalid_profiles_path, subfolder, "Missing required fields")
                #    invalid_count += 1
                #    scanned_count += 1
                #    continue

                expected_folder_name = f"{profile_id}"
                folder_name = os.path.basename(subfolder)
                if folder_name != expected_folder_name:
                    write_to_log(invalid_profiles_path, subfolder, "Folder name mismatch")
                    invalid_count += 1
                    scanned_count += 1
                    continue

                profile_id_exists = profile_id in config.sections()

                if profile_id_exists:
                    added_count += 1
                    scanned_count += 1
                    continue

                if not import_profile_dialog.listWidget.isEnabled():
                    import_profile_dialog.listWidget.setEnabled(True)
                profile_name = config_savetitan.get(profile_id, "name")
                executable_name = config_savetitan.get(profile_id, "executable_name")
                item_text = f"{profile_name} - {executable_name} ({profile_id})"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.UserRole, profile_id)
                item.setData(Qt.UserRole + 1, profile_info_file_path)
                import_profile_dialog.listWidget.addItem(item)
                can_import_count += 1
                scanned_count += 1

            if invalid_count == 0 and os.path.exists(invalid_profiles_path):
                os.remove(invalid_profiles_path)

            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("Scan Completed")
            message = f"Scan completed.<br><br>" \
                      f"Profiles scanned: {scanned_count}<br>"
            if added_count > 0:
                message += f"Profiles already added: {added_count}<br>"
            if invalid_count > 0:
                message += f"<br><font color='red'><b>Invalid profiles: {invalid_count}</b></font><br>"
                message += f"<font color='red'>(Logged to invalid_profiles.log)</font><br><br>"
            message += f"\nProfiles available for import: {can_import_count}"
            message_box.setTextFormat(Qt.RichText)
            message_box.setText(message)
            center_dialog_over_dialog(import_profile_dialog, message_box)
            message_box.exec_()
            
            import_profile_dialog.progressBar.reset()
            import_profile_dialog.progressBar.setMaximum(100)


        # Function to import selected profile to profiles.ini
        def import_selected_profile():
            selected_item = import_profile_dialog.listWidget.currentItem()
            if selected_item:
                profile_id = selected_item.data(Qt.UserRole)
                profile_path = selected_item.data(Qt.UserRole + 1)

                config = configparser.ConfigParser()
                config.read(profile_path)

                profile_id = config.sections()[0]
                profile_name = config.get(profile_id, "name")
                saves = config.get(profile_id, "saves")
                executable_name = config.get(profile_id, "executable_name")
                sync_mode = config.get(profile_id, "sync_mode")

                cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
                if not cloud_storage_path:
                    return

                profile_info_file_path = os.path.join(cloud_storage_path, profile_id, "profile_info.savetitan")
                profile_info_config = configparser.ConfigParser()
                profile_info_config.read(profile_info_file_path)
                save_slot = profile_info_config.get(profile_id, "save_slot")

                profiles_config = configparser.ConfigParser()
                profiles_config.read(profiles_config_file)

                for section in profiles_config.sections():
                    if profiles_config.get(section, 'name').lower() == profile_name.lower():
                        QMessageBox.critical(None, "Profile Already Exists", 
                                             "A profile with the same name already exists. Please change the name of the existing profile before importing this one.")
                        return

                if sys.platform == "win32":
                    file_filter = "Executable Files (*.exe *.bat *.cmd)"
                elif sys.platform == "darwin":
                    file_filter = "Executable Files (*.app *.command)"
                else:
                    file_filter = "Executable Files (*.sh *.AppImage)"

                if not network_share_accessible():
                    QMessageBox.critical(None, "Network Error", 
                                        "An error occurred while trying to access the network share. Please check your connection and try again.")
                    return

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

                profiles_config = configparser.ConfigParser()
                profiles_config.read(profiles_config_file)

                for section in profiles_config.sections():
                    if profiles_config.get(section, 'name').lower() == profile_name.lower():
                        QMessageBox.critical(None, "Profile Already Exists", "A profile with the same name already exists. Please change the name of the existing profile before importing this one.")
                        return

                io_config_file("profiles_file", "write", profile_id, "name", profile_name)
                io_config_file("profiles_file", "write", profile_id, "local_save_folder", local_save_folder)
                io_config_file("profiles_file", "write", profile_id, "game_executable", executable_path)
                io_config_file("profiles_file", "write", profile_id, "save_slot", save_slot)
                io_config_file("profiles_file", "write", profile_id, "saves", saves)
                io_config_file("profiles_file", "write", profile_id, "sync_mode", sync_mode)
                io_config_file("profiles_file", "write", profile_id, "executable_name", executable_name)
                io_config_file("profiles_file", "write", profile_id, "executable_path", executable_path)

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
        cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        try:
            profile_name = config.get(profile_id, "name")
        except configparser.NoOptionError:
            QMessageBox.warning(None, "Profile Not Found", "The selected profile was not found in the config file.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        try:
            profile_name = config.get(profile_id, "name")
        except configparser.NoOptionError:
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
        cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        try:
            profile_name = config.get(profile_id, "name")
        except configparser.NoOptionError:
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
                profile_data = io_config_file("profiles_file", "read", profile_id)
                profile_fields = profile_data[profile_id]
                name = profile_fields.get("name")
                game_executable = profile_fields.get("game_executable")
                local_save_folder = profile_fields.get("local_save_folder")
                save_slot = profile_fields.get("save_slot")
                sync_mode = profile_fields.get("sync_mode")
            except Exception as e:
                return
            try:
                dialog.profilenameField.setText(name)
                dialog.executableField.setText(game_executable)
                dialog.saveField.setText(local_save_folder)
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

        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        if profile_id not in config.sections():
            QMessageBox.warning(None, "Profile Not Found", "The selected profile does not exist.")
            return

        profile_name = dialog.profilenameField.text()
        local_save_folder = dialog.saveField.text()
        game_executable = dialog.executableField.text()
        sync_mode = config.get(profile_id, "sync_mode", fallback="Sync")

        for section in config.sections():
            if section != profile_id and config.get(section, 'name').lower() == profile_name.lower():
                QMessageBox.critical(None, "Profile Already Exists", 
                                     "A profile with the same name already exists. Please choose a different name.")
                return

        config.set(profile_id, "name", profile_name)
        config.set(profile_id, "local_save_folder", local_save_folder)
        config.set(profile_id, "game_executable", game_executable)
        config.set(profile_id, "sync_mode", sync_mode)
        save_config_file(config)

        profile_folder = os.path.join(cloud_storage_path, profile_id)

        profile_info_file_path = os.path.join(cloud_storage_path, profile_id, "profile_info.savetitan")
        profile_info_config = configparser.ConfigParser()
        profile_info_config.read(profile_info_file_path)
        save_slot = profile_info_config.get(profile_id, "save_slot")

        profile_info_config.set(profile_id, "name", profile_name)

        profile_info_config.set(profile_id, "executable_name", os.path.basename(game_executable))

        with open(profile_info_file_path, "w") as file:
            profile_info_config.write(file)

        configprofileView.model().sourceModel()._data = load_data_into_model_data()
        
        for i in range(configprofileView.model().rowCount(QtCore.QModelIndex())):
            if configprofileView.model().sourceModel()._data[i][2] == profile_id:
                new_index = configprofileView.model().index(i, 0)
                configprofileView.setCurrentIndex(new_index)
                update_fields(new_index)
                break

        QMessageBox.information(None, "Profile Saved", "The profile has been successfully saved.")


    # Function to save field information to selected profile
    def save_profile_fields():
        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to save the fields.")
            return

        selected_row_data = configprofileView.model().sourceModel()._data[selected_index.row()]
        profile_id = selected_row_data[2]

        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        if profile_id not in config.sections():
            QMessageBox.warning(None, "Profile Not Found", "The selected profile does not exist.")
            return

        profile_name = dialog.profilenameField.text()
        local_save_folder = dialog.saveField.text()
        game_executable = dialog.executableField.text()
        sync_mode = config.get(profile_id, "sync_mode", fallback="Sync")

        for section in config.sections():
            if section != profile_id and config.get(section, 'name').lower() == profile_name.lower():
                QMessageBox.critical(None, "Profile Already Exists", 
                                     "A profile with the same name already exists. Please choose a different name.")
                return

        config.set(profile_id, "name", profile_name)
        config.set(profile_id, "local_save_folder", local_save_folder)
        config.set(profile_id, "game_executable", game_executable)
        config.set(profile_id, "sync_mode", sync_mode)
        save_config_file(config)

        profile_folder = os.path.join(cloud_storage_path, profile_id)

        profile_info_file_path = os.path.join(profile_folder, "profile_info.savetitan")
        profile_info_config = configparser.ConfigParser()
        profile_info_config.read(profile_info_file_path)

        profile_info_config.set(profile_id, "name", profile_name)

        profile_info_config.set(profile_id, "executable_name", os.path.basename(game_executable))

        with open(profile_info_file_path, "w") as file:
            profile_info_config.write(file)

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
        local_save_folder = io_config_file("profiles_file", "read", profile_id, "local_save_folder")
        QDesktopServices.openUrl(QUrl.fromLocalFile(local_save_folder))


    # Function to open a cloud storage location in file explorer
    def open_cloud_location_storage(profile_id):
        cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
        folder_path = os.path.join(cloud_storage_path, profile_id)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))


    # Function to create context menu
    def context_menu(point):
        menu = QMenu()

        open_cloud_storage_action = QAction("Open Cloud Storage", menu)
        open_local_save_action = QAction("Open Local Save", menu)
        delete_profile_action = QAction("Delete Profile", menu)
        open_save_mgmt_action = QAction("Open Save Manager", menu)
        copy_profile_id_action = QAction("Copy Profile ID", menu)

        index = configprofileView.indexAt(point)
        
        if index.isValid():
            selected_profile_id = configprofileView.model().sourceModel()._data[index.row()][2]

            open_cloud_storage_action.triggered.connect(lambda: open_cloud_location_storage(selected_profile_id))
            open_local_save_action.triggered.connect(lambda: open_local_save_location(selected_profile_id))
            delete_profile_action.triggered.connect(lambda: remove_profile(selected_profile_id))
            open_save_mgmt_action.triggered.connect(lambda: save_mgmt_dialog(selected_profile_id))
            copy_profile_id_action.triggered.connect(lambda: QApplication.clipboard().setText(selected_profile_id))

            menu.addAction(open_local_save_action)
            menu.addAction(open_cloud_storage_action)
            menu.addSeparator()
            menu.addAction(open_save_mgmt_action)
            menu.addSeparator()
            menu.addAction(delete_profile_action)
            menu.addSeparator()
            menu.addAction(copy_profile_id_action)

            menu.exec_(configprofileView.viewport().mapToGlobal(point))

    configprofileView.setContextMenuPolicy(Qt.CustomContextMenu)
    configprofileView.customContextMenuRequested.connect(context_menu)
    
    configprofileView.selectionModel().currentChanged.connect(update_fields)

    dialog.actionNew_Profile.triggered.connect(add_profile)
    dialog.actionExit.triggered.connect(dialog.close)
    dialog.actionAbout.triggered.connect(lambda: about_dialog(dialog))

    dialog.show()


# REFACTORED FUNCTION: Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-runprofile", help="Specify the game profile to be used")
parser.add_argument("-runid", help="Specify the profile ID to be used")
parser.add_argument("-list", action='store_true', help="List all profiles in profiles.ini")
args = parser.parse_args()

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

app = QApplication([])
profile_data = None

cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

if args.list:
    profiles = io_config_file("profiles_file", "read")
    if profiles is None:
        print("No profiles found in profiles.ini")
        sys.exit(1)
    else:
        for profile_id, profile_data in profiles.items():
            name = profile_data.get('name')
            save_slot = profile_data.get('save_slot')
            print(f"{profile_id} - {name} - Save Slot: {save_slot}")
        sys.exit(1)
elif args.runprofile:
    profile_id = io_config_file("profiles_file", "read", None, "name", args.runprofile)
    if not profile_id:
        print("The specified game profile does not exist in profiles.ini")
        sys.exit(1)
    else:
        profile_data = io_config_file("profiles_file", "read", profile_id)
        if not profile_data or profile_id not in profile_data:
            sys.exit(1)
        
        profile_fields = profile_data[profile_id]
        name = profile_fields.get("name")
        local_save_folder = profile_fields.get("local_save_folder")
        game_executable = profile_fields.get("game_executable")
        save_slot = profile_fields.get("save_slot")
        sync_mode = profile_fields.get("sync_mode")

        if not cloud_storage_path:
            print("Cloud storage path is not configured. Run the script without a parameter to run the first-time setup")
            sys.exit(1)

        game_profile_folder = os.path.join(cloud_storage_path, f"{profile_id}")
        check_and_sync_saves(name, local_save_folder, game_executable, save_slot, profile_id)
elif args.runid:
    if not cloud_storage_path:
        print("Cloud storage path is not configured. Run the script without a parameter to run the first-time setup")
        sys.exit(1)

    profile_id = args.runid
    profile_data = io_config_file("profiles_file", "read", profile_id)

    if not profile_data or profile_id not in profile_data:
        sys.exit(1)

    profile_fields = profile_data[profile_id]

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
    
app.exec_()