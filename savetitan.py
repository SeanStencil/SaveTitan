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
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QInputDialog
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QTimer, QAbstractTableModel, QModelIndex

# Get the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the config file path
profiles_config_file = os.path.join(script_dir, "profiles.ini")
global_config_file = os.path.join(script_dir, "global.ini")

# Define Global Variables
global cloud_storage_path

# Generate a 16 character string for use for profile_id's
def generate_id():
    characters = string.ascii_letters + string.digits
    id_length = 16
    random_id = ''.join(random.choices(characters, k=id_length))
    return random_id

# Check a function's ability to read the file/folder path
def check_read_permissions(path, file_type):
    if not os.access(path, os.R_OK):
        QMessageBox.critical(None, "Access Denied", 
                             f"Permission denied to read the {file_type}. Please check the file permissions and try again.")
        return False
    return True

# Check a function's ability to read the file/folder path
def check_execute_permissions(path, file_type):
    if not os.access(path, os.X_OK):
        QMessageBox.critical(None, "Access Denied", 
                             f"Permission denied to read the {file_type}. Please check the file permissions and try again.")
        return False
    return True

# Check a function's ability to write the file/folder path
def check_write_permissions(path, name):
    if os.access(path, os.W_OK):
        return True
    else:
        QMessageBox.critical(None, "Access Denied",
                             f"Permission denied to write to the {name}. Please check the file permissions and try again.")
        return False

# Export a .savetitan file for the profile folder in cloud storage
def export_profile_info(profile_name, save_slot, saves, profile_id, sync_mode, executable_name):
    global cloud_storage_path

    folder_path = os.path.join(cloud_storage_path, profile_id)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, "profile_info.savetitan")
    config = configparser.ConfigParser()
    config[profile_id] = {
        "name": profile_name,
        "save_slot": str(save_slot),
        "saves": str(saves),
        "sync_mode": sync_mode,
        "executable_name": executable_name
    }

    config.remove_option(profile_id, "profile_id")

    with open(file_path, "w") as file:
        config.write(file)

# Perform backup function prior to sync
def make_backup_copy(original_folder):
    backup_folder = original_folder + ".bak"
    
    if os.path.exists(backup_folder):
        shutil.rmtree(backup_folder)
        
    shutil.copytree(original_folder, backup_folder)

# Function to check and sync saves
def check_and_sync_saves(name, local_save_folder, game_executable, save_slot, profile_id):
    if not os.path.exists(local_save_folder):
        QMessageBox.critical(None, "Save Folder Not Found", "Local save folder does not exist. Please make sure your existing save files are located in the correct folder.")
        return
    if not check_read_permissions(local_save_folder, 'Local Save Folder'):
        return
    if not check_read_permissions(game_executable, 'Game Executable') or not check_write_permissions(game_executable, 'Game Executable'):
        return
    config = configparser.ConfigParser()
    config.read(global_config_file)
    cloud_storage_path = config.get("Global Settings", "cloud_storage_path")
    game_profile_folder_save_slot = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)
    if os.path.exists(game_profile_folder_save_slot) and os.listdir(game_profile_folder_save_slot):
        local_save_time = datetime.datetime.fromtimestamp(os.path.getmtime(local_save_folder))
        cloud_save_time = datetime.datetime.fromtimestamp(os.path.getmtime(game_profile_folder_save_slot))

        comparison = filecmp.dircmp(local_save_folder, game_profile_folder_save_slot)
        if comparison.left_list == comparison.right_list and not comparison.diff_files and not comparison.common_funny:
            launch_game(game_executable, save_slot)
        else:
            local_save_time_str = local_save_time.strftime("%B %d, %Y, %I:%M:%S %p")
            cloud_save_time_str = cloud_save_time.strftime("%B %d, %Y, %I:%M:%S %p")

            if local_save_time > cloud_save_time:
                reply = QMessageBox.question(None, "LOCAL SAVE IS NEWER",
                                             f"The local save (last modified: {local_save_time_str}) is newer than the one in cloud storage (last modified: {cloud_save_time_str}). Do you want to keep your local save?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    launch_game(game_executable, save_slot)
                else:
                    sync_save_local(args.runprofile)
                    launch_game(game_executable, save_slot)
            else:
                reply = QMessageBox.question(None, "CLOUD SAVE IS NEWER",
                                             f"The cloud save (last modified: {cloud_save_time_str}) is newer than the one in local save (last modified: {local_save_time_str}). Do you want to download your cloud save?",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    sync_save_local(args.runprofile)
                    launch_game(game_executable, save_slot)
                else:
                    launch_game(game_executable, save_slot)
    else:
        launch_game(game_executable, save_slot)

# Function to sync saves (copy local saves to cloud storage)
def sync_save_cloud(game_profile, save_slot): 
    save_folder = os.path.join(game_profile_folder + "/save" + save_slot)
    
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    make_backup_copy(save_folder)

    shutil.rmtree(save_folder)
    shutil.copytree(local_save_folder, save_folder)

# Function to sync saves (copy Cloud saves to local storage)
def sync_save_local(game_profile):

    make_backup_copy(local_save_folder)

    shutil.rmtree(local_save_folder)
    shutil.copytree(game_profile_folder, local_save_folder)

# Function to launch the game
def launch_game(game_executable, save_slot):
    if not check_execute_permissions(game_executable, 'game executable'):
        return

    subprocess.Popen(game_executable)

    def handle_dialog_response():
        dialog_result = QMessageBox.information(None, "Game in Progress", "Please click 'I'm done' when you have finished playing.")
        if dialog_result == QMessageBox.Ok:
            sync_save_cloud(args.runprofile, save_slot)

    QTimer.singleShot(0, handle_dialog_response)

# Read the profiles configuration file and retrieve the profile information
def read_config_file(profile):
    config = configparser.ConfigParser()
    config.read(profiles_config_file)
    required_fields = ["name", "local_save_folder", "game_executable", "save_slot", "saves", "sync_mode"]
    
    if not config.has_section(profile):
        return None

    for field in required_fields:
        if not config.has_option(profile, field):
            return None

    name = config.get(profile, "name")
    local_save_folder = config.get(profile, "local_save_folder")
    game_executable = config.get(profile, "game_executable")
    save_slot = config.get(profile, "save_slot")
    saves = config.get(profile, "saves")
    sync_mode = config.get(profile, "sync_mode")

    return name, local_save_folder, game_executable, save_slot, saves, sync_mode

# Save the profiles configuration file with updated profile information
def save_config_file(config):
    field_order = ["name", "game_executable", "local_save_folder", "saves", "save_slot", "sync_mode"]

    ordered_config = configparser.ConfigParser(interpolation=None)

    for section in config.sections():
        ordered_config.add_section(section)
        for field in field_order:
            if field in config[section]:
                value = config[section][field]
                ordered_config.set(section, field, value)

    with open(profiles_config_file, "w") as file:
        ordered_config.write(file)

# Read the global configuration file and retrieve the global settings
def read_global_config():
    global cloud_storage_path  # declare that we are using the global variable
    config = configparser.ConfigParser()
    config.read(global_config_file)
    cloud_storage_path = config.get('Global Settings', 'cloud_storage_path', fallback=None)
    return cloud_storage_path

# Function to set the cloud storage location
def set_cloud_storage_path():
    while True:
        cloud_storage_path = QFileDialog.getExistingDirectory(None, "Select Cloud Storage Path")
        if not cloud_storage_path:
            break

        subfolders = [f.path for f in os.scandir(cloud_storage_path) if f.is_dir()]
        savetitan_files_found = False
        for subfolder in subfolders:
            savetitan_files = glob.glob(os.path.join(subfolder, "*.savetitan"))
            if len(savetitan_files) > 0:
                savetitan_files_found = True
                break

        if not savetitan_files_found:
            if len(os.listdir(cloud_storage_path)) > 0:
                response = QMessageBox.warning(None, "Non-Empty Cloud Storage Path",
                                               "WARNING: The selected cloud storage path is not empty. Choose another directory?",
                                               QMessageBox.Yes | QMessageBox.No)
                if response == QMessageBox.Yes:
                    continue

        config = configparser.ConfigParser()
        config["Global Settings"] = {"cloud_storage_path": cloud_storage_path}
        with open(global_config_file, "w") as file:
            config.write(file)
        break

    dialog.addButton.setEnabled(True)
    dialog.importButton.setEnabled(True)

# Function to show config dialog
def show_config_dialog(config):
    global dialog
    dialog = uic.loadUi("config.ui")
    dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
    dialog.setFixedSize(671, 533)

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

    configprofileView.verticalHeader().setVisible(False)

    headers = ["Profile Name", "Saves", "Mode", "ID"]

    data = []
    for section in config.sections():
        if section != "Global Settings":
            try:
                profile_name = config.get(section, "name")
                saves = config.get(section, "saves")
                sync_mode = config.get(section, "sync_mode")
                profile_id = section
                data.append([profile_name, saves, sync_mode, profile_id])
            except configparser.NoOptionError:
                continue

    configprofileView.setModel(TableModel(data, headers))

    header = configprofileView.horizontalHeader()

    header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
    header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

    configprofileView.resizeRowsToContents()

    if configprofileView.model().rowCount(QModelIndex()) > 0:
        selected_index = configprofileView.currentIndex()
        selected_row_data = configprofileView.model()._data[selected_index.row()]
        selected_profile_id = selected_row_data[3]

    cloud_storage_path = read_global_config()
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
        elif not check_write_permissions(cloud_storage_path, 'Cloud Storage Path'):
            dialog.addButton.setEnabled(False)
            dialog.importButton.setEnabled(False)
            dialog.removeButton.setEnabled(False)
            dialog.actionNewProfile.setEnabled(False)
            dialog.actionRemoveProfile.setEnabled(False)
            dialog.actionImportProfile.setEnabled(False)

    # Load profiles from config into table model
    def load_data_into_table_model():
        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        data = []

        for section in config.sections():
            if section != "Global Settings":
                name = config.get(section, "name")
                saves = config.get(section, "saves")
                sync_mode = config.get(section, "sync_mode")
                profile_id = section

                data.append([name, saves, sync_mode, profile_id])

        model = TableModel(data, headers)

        # Setting the model to the view
        configprofileView.setModel(model)

        return model
    
    def load_data_into_model_data():
        profiles_config = configparser.ConfigParser()
        profiles_config.read(profiles_config_file)

        data = []
        for section in profiles_config.sections():
            profile = profiles_config[section]
            name = profile.get("name")
            saves = profile.get("saves")
            sync_mode = profile.get("sync_mode")

            row = [name, saves, sync_mode, section]
            
            data.append(row)

        return data

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

        config_settings_dialog_pos = dialog.pos()
        config_settings_dialog_size = dialog.size()

        global_settings_dialog_width = global_settings_dialog.frameGeometry().width()
        global_settings_dialog_height = global_settings_dialog.frameGeometry().height()
        x = int(config_settings_dialog_pos.x() + (config_settings_dialog_size.width() - global_settings_dialog_width) / 2)
        y = int(config_settings_dialog_pos.y() + (config_settings_dialog_size.height() - global_settings_dialog_height) / 2)

        global_settings_dialog.move(x, y)

        global_settings_dialog.exec_()

    # Function to add a profile
    def add_profile():
        cloud_storage_path = read_global_config()
        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        if not cloud_storage_path:
            QMessageBox.warning(None, "Cloud Storage Path Not Found", "Cloud storage path is not configured. Please configure it.")
            return

        if not os.path.exists(cloud_storage_path):
            return

        config_dialog = QApplication.activeWindow()

        profile_dialog = QInputDialog(config_dialog)
        profile_dialog.setWindowTitle("Add Profile")
        profile_dialog.setLabelText("Enter the profile name:")
        profile_dialog.setWindowModality(Qt.WindowModal)

        if profile_dialog.exec_() == QInputDialog.Accepted:
            profile_name = profile_dialog.textValue().strip()
            if profile_name:
                existing_profiles = [section for section in config.sections() if config.get(section, 'name').lower() == profile_name.lower()]
                if existing_profiles:
                    QMessageBox.critical(None, "Profile Already Exists", "A profile with the same name already exists. Please choose a different name.")
                    return

                if sys.platform == "win32":
                    file_filter = "Executable Files (*.exe *.bat *.cmd)"
                elif sys.platform == "darwin":
                    file_filter = "Executable Files (*.app *.command)"
                else:
                    file_filter = "Executable Files (*.sh *.AppImage))"

                game_executable, ok = QFileDialog.getOpenFileName(config_dialog, "Add Profile - Locate the executable for " + profile_name, filter=file_filter)
                if not ok:
                    return

                executable_name = os.path.basename(game_executable)

                local_save_folder = QFileDialog.getExistingDirectory(config_dialog, "Add Profile - Locate the save folder for " + profile_name, options=QFileDialog.ShowDirsOnly)
                if not local_save_folder:
                    return

                profile_id = None
                while True:
                    profile_id = generate_id()
                    if not any(profile_id == section for section in config.sections()):
                        break

                save_slot = 1
                saves = 1
                sync_mode = "Sync"

                config[profile_id] = {
                    "name": profile_name,
                    "local_save_folder": local_save_folder,
                    "game_executable": game_executable,
                    "save_slot": str(save_slot),
                    "saves": str(saves),
                    "sync_mode": sync_mode,
                }
                save_config_file(config)

                new_row_data = [profile_name, str(saves), sync_mode, profile_id]
                configprofileView.model()._data.append(new_row_data)

                configprofileView.model().layoutChanged.emit()

                profile_folder = os.path.join(cloud_storage_path, profile_id)
                os.makedirs(profile_folder, exist_ok=True)
                export_profile_info(profile_name, save_slot, saves, profile_id, sync_mode, executable_name)

    # Function to remove a profile
    def remove_profile():
        selected_index = configprofileView.selectionModel().currentIndex()
        if selected_index.isValid():
            selected_profile = configprofileView.model()._data[selected_index.row()][0]
            confirm = QMessageBox.question(None, "Remove Profile", f"Are you sure you want to remove the profile '{selected_profile}'?", QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                config = configparser.ConfigParser()
                config.read(profiles_config_file)

                profile_id_to_remove = configprofileView.model()._data[selected_index.row()][3]

                if profile_id_to_remove in config.sections():
                    config.remove_section(profile_id_to_remove)
                    with open(profiles_config_file, 'w') as configfile:
                        config.write(configfile)

                    configprofileView.model()._data.pop(selected_index.row())
                    configprofileView.model().layoutChanged.emit()
                else:
                    QMessageBox.warning(None, "Profile Not Found", f"The profile '{selected_profile}' was not found in the configuration file.")
            else:
                return
        else:
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to remove.")

    # Function to open import profile dialog
    def import_profile_dialog():
        cloud_storage_path = read_global_config()

        if not cloud_storage_path:
            QMessageBox.warning(None, "Cloud Storage Path Not Found", "Cloud storage path is not configured. Please configure it.")
            return

        if not os.path.exists(cloud_storage_path):
            return

        import_profile_dialog = uic.loadUi("import_profile.ui")
        import_profile_dialog.setWindowFlags(import_profile_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        import_profile_dialog.setFixedSize(491, 331)

        import_profile_dialog.importButton.setEnabled(False)

        def scan_cloud_storage():
            scanned_count = 0
            added_count = 0
            invalid_count = 0
            can_import_count = 0

            with open('import_scan.log', 'a') as file:
                file.truncate(0)
            logging.basicConfig(filename='import_scan.log', filemode='w', level=logging.INFO,
                                format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

            import_profile_dialog.listWidget.clear()

            cloud_storage_path = read_global_config()
            if not cloud_storage_path:
                return

            config = configparser.ConfigParser()
            config.read(profiles_config_file)

            subfolders = [f.path for f in os.scandir(cloud_storage_path) if f.is_dir() and f.name != "invalid_profiles"]
            invalid_profiles_dir = os.path.join(cloud_storage_path, "invalid_profiles")
            os.makedirs(invalid_profiles_dir, exist_ok=True)

            import_profile_dialog.progressBar.setMaximum(len(subfolders))

            for subfolder in subfolders:
                profile_info_file_path = os.path.join(subfolder, "profile_info.savetitan")
                if not os.path.exists(profile_info_file_path):
                    move_to_invalid(invalid_profiles_dir, subfolder)
                    invalid_count += 1
                    scanned_count += 1
                    continue

                config_savetitan = configparser.ConfigParser()
                config_savetitan.read(profile_info_file_path)

                if not config_savetitan.sections():
                    move_to_invalid(invalid_profiles_dir, subfolder)
                    invalid_count += 1
                    scanned_count += 1
                    continue

                profile_id = config_savetitan.sections()[0]
                required_fields = ['name', 'save_slot', 'saves', 'sync_mode', 'executable_name']
                if not all(config_savetitan.has_option(profile_id, field) for field in required_fields):
                    move_to_invalid(invalid_profiles_dir, subfolder)
                    invalid_count += 1
                    scanned_count += 1
                    continue

                expected_folder_name = f"{profile_id}"
                folder_name = os.path.basename(subfolder)
                if folder_name != expected_folder_name:
                    move_to_invalid(invalid_profiles_dir, subfolder)
                    invalid_count += 1
                    scanned_count += 1
                    continue

                profile_id_exists = profile_id in config.sections()

                if profile_id_exists:
                    added_count += 1
                    scanned_count += 1
                    continue

                profile_name = config_savetitan.get(profile_id, "name")
                executable_name = config_savetitan.get(profile_id, "executable_name")
                item_text = f"{profile_name} ({executable_name}) - {profile_id}"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setData(Qt.UserRole, profile_id)
                item.setData(Qt.UserRole + 1, profile_info_file_path)
                import_profile_dialog.listWidget.addItem(item)
                can_import_count += 1
                scanned_count += 1

                import_profile_dialog.progressBar.setValue(import_profile_dialog.progressBar.value() + 1)

            import_profile_dialog.progressBar.setValue(0)

            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Information)
            message_box.setWindowTitle("Scan Completed")
            message_box.setText(f"Scan completed.\n\n"
                                f"Profiles scanned: {scanned_count}\n"
                                f"Profiles already added: {added_count}\n"
                                f"Invalid profiles moved to invalid_profiles: {invalid_count}\n"
                                f"\n"
                                f"Profiles available for import: {can_import_count}")
            message_box.exec_()

        def move_to_invalid(invalid_profiles_dir, subfolder):
            new_path = os.path.join(invalid_profiles_dir, os.path.basename(subfolder))
            shutil.move(subfolder, new_path)
            logging.info(f"Invalid: {subfolder}")

        def import_selected_profile():
            selected_item = import_profile_dialog.listWidget.currentItem()
            if selected_item:
                profile_id = selected_item.data(Qt.UserRole)
                profile_path = selected_item.data(Qt.UserRole + 1)

                config = configparser.ConfigParser()
                config.read(profile_path)

                profile_id = config.sections()[0]
                profile_name = config.get(profile_id, "name")
                save_slot = config.get(profile_id, "save_slot")
                saves = config.get(profile_id, "saves")
                executable_name = config.get(profile_id, "executable_name")
                sync_mode = config.get(profile_id, "sync_mode")

                if sys.platform == "win32":
                    file_filter = "Executable Files (*.exe *.bat *.cmd)"
                elif sys.platform == "darwin":
                    file_filter = "Executable Files (*.app *.command)"
                else:
                    file_filter = "Executable Files (*.sh *.AppImage)"

                executable_path, _ = QFileDialog.getOpenFileName(import_profile_dialog,
                                                                 "Import Profile - Locate the executable for " + executable_name,
                                                                 filter=file_filter)
                if not executable_path:
                    return

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

                profiles_config = configparser.ConfigParser()
                profiles_config.read(profiles_config_file)

                profiles_config[profile_id] = {
                    "name": profile_name,
                    "save_slot": save_slot,
                    "saves": saves,
                    "sync_mode": sync_mode,
                    "executable_name": executable_name,
                    "executable_path": executable_path
                }

                with open(profiles_config_file, 'w') as configfile:
                    profiles_config.write(configfile)

                local_save_folder = QFileDialog.getExistingDirectory(import_profile_dialog,
                                                                     "Import Profile - Locate the save folder for " + profile_name,
                                                                     options=QFileDialog.ShowDirsOnly)
                if not local_save_folder:
                    return

                config = configparser.ConfigParser()
                config.read(profiles_config_file)

                section_name = profile_id
                config[section_name] = {
                    "name": profile_name,
                    "local_save_folder": local_save_folder,
                    "game_executable": executable_path,
                    "save_slot": save_slot,
                    "saves": saves,
                    "sync_mode": sync_mode,
                }

                with open(profiles_config_file, "w") as file:
                    config.write(file)

                QMessageBox.information(None, "Success", "Profile imported successfully.")
                new_row_data = [profile_name, saves, sync_mode, profile_id]
                configprofileView.model()._data.append(new_row_data)
                configprofileView.model().layoutChanged.emit()

                import_profile_dialog.close()

        import_profile_dialog.scanButton.clicked.connect(scan_cloud_storage)
        import_profile_dialog.importButton.clicked.connect(import_selected_profile)
        import_profile_dialog.closeButton.clicked.connect(import_profile_dialog.close)

        import_profile_dialog.listWidget.currentItemChanged.connect(lambda: import_profile_dialog.importButton.setEnabled(True if import_profile_dialog.listWidget.currentItem() else False))

        config_dialog_pos = dialog.pos()
        config_dialog_size = dialog.size()

        import_dialog_width = import_profile_dialog.frameGeometry().width()
        import_dialog_height = import_profile_dialog.frameGeometry().height()
        x = int(config_dialog_pos.x() + (config_dialog_size.width() - import_dialog_width) / 2)
        y = int(config_dialog_pos.y() + (config_dialog_size.height() - import_dialog_height) / 2)

        import_profile_dialog.move(x, y)

        import_profile_dialog.exec_()
        
    # Show the about dialog window
    def about_dialog():
        about = QMessageBox()
        about.setWindowIcon(QIcon('icon/path'))
        about.setWindowTitle("About SaveTitan")
        about.setText("SaveTitan\n\nSaveTitan is a game save management tool that allows you to sync your game saves between local storage and cloud storage.\n\nDeveloped by Sean Bowman")
        about.exec_()

    def update_executable():
        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model()._data[selected_index.row()]
        profile_id = selected_row_data[3]

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

        filepath, _ = QFileDialog.getOpenFileName(None, f"Edit Profile - Locate the executable for {profile_name}", filter=file_filter)

        if filepath:
            dialog.executableField.setText(filepath)

    def update_local_save_folder():
        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to edit.")
            return

        selected_row_data = configprofileView.model()._data[selected_index.row()]
        profile_id = selected_row_data[3]

        try:
            profile_name = config.get(profile_id, "name")
        except configparser.NoOptionError:
            QMessageBox.warning(None, "Profile Not Found", "The selected profile was not found in the config file.")
            return

        save_folder = QFileDialog.getExistingDirectory(None, f"Edit Profile - Locate the save folder for {profile_name}", options=QFileDialog.ShowDirsOnly)
        
        if save_folder:
            dialog.saveField.setText(save_folder)

    def update_saveslot_combo():
        selected_index = configprofileView.currentIndex()
        if selected_index.isValid():
            profile_id = configprofileView.model()._data[selected_index.row()][4]
            profiles_config = configparser.ConfigParser()
            profiles_config.read(profiles_config_file)
            
            try:
                profile = profiles_config[profile_id]
                save_slot = profile.get("save_slot")
                saves = profile.get("saves")
            except Exception as e:
                QMessageBox.warning(None, "Profile Not Found", "The selected profile was not found in the config file.")
                return
        
        dialog.saveslotCombo.clear()
        for i in range(1, int(saves) + 1):
            item_text = f"Save {i}"
            dialog.saveslotCombo.addItem(item_text)
        
        dialog.saveslotCombo.setCurrentIndex(int(save_slot) - 1)

    def update_fields(index):
        if index.isValid():
            row_data = configprofileView.model()._data[index.row()]
            profile_id = row_data[3]

            try:
                name, local_save_folder, game_executable, save_slot, saves, sync_mode = read_config_file(profile_id)
            except Exception as e:
                return

            try:
                dialog.profilenameField.setText(name)
                dialog.executableField.setText(game_executable)
                dialog.saveField.setText(local_save_folder)
            except Exception as e:
                return

            try:
                dialog.saveslotCombo.clear()
                for slot in range(1, int(saves) + 1):
                    dialog.saveslotCombo.addItem(f'Save {slot}')

                combo_index = dialog.saveslotCombo.findText(f'Save {save_slot}')
                if combo_index != -1:
                    dialog.saveslotCombo.setCurrentIndex(combo_index)
            except Exception as e:
                return

    def save_profile_fields():
        selected_index = configprofileView.currentIndex()
        if not selected_index.isValid():
            QMessageBox.warning(None, "No Profile Selected", "Please select a profile to save the fields.")
            return

        selected_row_data = configprofileView.model()._data[selected_index.row()]
        profile_id = selected_row_data[3]

        config = configparser.ConfigParser()
        config.read(profiles_config_file)

        if profile_id not in config.sections():
            QMessageBox.warning(None, "Profile Not Found", "The selected profile does not exist.")
            return

        profile_name = dialog.profilenameField.text()
        local_save_folder = dialog.saveField.text()
        game_executable = dialog.executableField.text()
        save_slot = int(dialog.saveslotCombo.currentText().split()[1])
        sync_mode = config.get(profile_id, "sync_mode", fallback="Sync")

        config.set(profile_id, "name", profile_name)
        config.set(profile_id, "local_save_folder", local_save_folder)
        config.set(profile_id, "game_executable", game_executable)
        config.set(profile_id, "save_slot", str(save_slot))
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

        configprofileView.model()._data = load_data_into_model_data()
        
        for i in range(configprofileView.model().rowCount(QtCore.QModelIndex())):
            if configprofileView.model()._data[i][3] == profile_id:
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
    
    # Connections for configprofileView clicks
    configprofileView.selectionModel().currentChanged.connect(update_fields)

    # Connections for menu actions
    dialog.actionNew_Profile.triggered.connect(add_profile)
    dialog.actionExit.triggered.connect(dialog.close)
    dialog.actionAbout.triggered.connect(about_dialog)

    dialog.show()

# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-runprofile", help="Specify the game profile to be used")
args = parser.parse_args()

app = QApplication([])

if args.runprofile:
    config = configparser.ConfigParser()
    config.read(profiles_config_file)
    cloud_storage_path = read_global_config()

    # The keys in the config are now profile_id, not names. So, we need to check the 'name' field.
    existing_profiles = [section for section in config.sections() if config[section]['name'].lower() == args.runprofile.lower()]
    if not existing_profiles:
        print("The specified game profile does not exist in profiles.ini")
        sys.exit(1)
    else:
        profile_id = existing_profiles[0]
        name, local_save_folder, game_executable, save_slot, saves, sync_mode = read_config_file(profile_id)

        game_profile_folder = os.path.join(cloud_storage_path, f"{profile_id}")

        if not cloud_storage_path:
            print("Cloud storage path is not configured. Please run the script with the 'global' argument to configure it")
            sys.exit(1)
        else:
            check_and_sync_saves(name, local_save_folder, game_executable, save_slot, profile_id)
else:
    config = configparser.ConfigParser()
    config.read(profiles_config_file)
    show_config_dialog(config)

app.exec_()