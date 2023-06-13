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


# REFACTORED FUNCTION: Get the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))


# REFACTORED FUNCTION: Define the config file path
profiles_config_file = os.path.join(script_dir, "profiles.ini")
global_config_file = os.path.join(script_dir, "global.ini")


# REFACTORED FUNCTION: Check a function's ability to perform the given action (read, write, execute) on the file/folder path
def check_permissions(path, file_type, action):
    actions = {
        "read": os.R_OK,
        "write": os.W_OK,
        "execute": os.X_OK
    }

    if not os.access(path, actions[action]):
        QMessageBox.critical(None, "Access Denied",
                             f"Permission denied to {action} the {file_type}. Please check the file permissions and try again.")
        return False
    return True


# Try and wake up the network location
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

    if config_type == "profiles_file" and not config.has_section(profile_id):
        return None

    if read_write_mode == "read":
        if not field:
            return {s: dict(config.items(s)) for s in config.sections()}
        else:
            return config.get(config_section, field) if config.has_option(config_section, field) else None

    elif read_write_mode == "write":

        if not check_permissions(config_file, config_type, "write"):
            raise PermissionError(f"Permission denied to write to the {config_type}.")

        if not field:
            raise ValueError("Field must be specified in 'write' mode.")
        config.set(profile_id, field, write_value or "")
        with open(config_file, "w") as file:
            config.write(file)


# REFACTORED FUNCTION: Function to read and write the profile_info.savetitan file in the cloud storage location
def io_savetitan_file(global_config_file, read_write_mode, profile_id, field, write_value=None):
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


# Function to sync saves (Copy local saves to cloud storage)
def sync_save_cloud(profile_id):
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")
    save_slot = io_config_file("profiles_file", "read", profile_id, "save_slot")
    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id + "/save" + save_slot)
    if not network_share_accessible():
        return
    while True:
        try:
            os.makedirs(cloud_profile_save_path, exist_ok=True)
            
            make_backup_copy(cloud_profile_save_path)
            
            shutil.rmtree(cloud_profile_save_path)
            shutil.copytree(local_save_folder, cloud_profile_save_path)
            
            comparison = filecmp.dircmp(local_save_folder, cloud_profile_save_path)

            if comparison.left_list == comparison.right_list and not comparison.diff_files and not comparison.common_funny:
                match, mismatch, errors = filecmp.cmpfiles(local_save_folder, cloud_profile_save_path, comparison.common_files)
                if len(mismatch) == 0 and len(errors) == 0:
                    print("Sync completed successfully.")
                    break
            else:
                raise Exception("Mismatch in directory contents")
        except Exception as e:
            reply = QMessageBox.critical(None, "Sync Error",
                                         f"An error occurred during the sync process: {str(e)}",
                                         QMessageBox.Retry | QMessageBox.Abort, QMessageBox.Retry)
            if reply != QMessageBox.Retry:
                break


# Function to sync saves (Copy cloud saves to local storage)
def sync_save_local(profile_id, save_slot):
    local_save_folder = io_config_file("profiles_file", "read", profile_id, "local_save_path")
    cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

    source_folder = os.path.join(cloud_storage_path, profile_id, "save" + save_slot)
    destination_folder = local_save_folder

    if not network_share_accessible():
        return

    while True:
        try:
            os.makedirs(destination_folder, exist_ok=True)

            make_backup_copy(destination_folder)

            if check_permissions(destination_folder, 'destination folder', "write") and check_permissions(source_folder, 'source folder', "read"):
                shutil.rmtree(destination_folder)
                shutil.copytree(source_folder, destination_folder)

                comparison = filecmp.dircmp(source_folder, destination_folder)

                if comparison.left_list == comparison.right_list and not comparison.diff_files and not comparison.common_funny:
                    match, mismatch, errors = filecmp.cmpfiles(source_folder, destination_folder, comparison.common_files)
                    if len(mismatch) == 0 and len(errors) == 0:
                        break
                else:
                    raise Exception("Mismatch in directory contents")
        except Exception as e:
            reply = QMessageBox.critical(None, "Sync Error",
                                         f"An error occurred during the sync process: {str(e)}",
                                         QMessageBox.Retry | QMessageBox.Abort, QMessageBox.Retry)
            if reply != QMessageBox.Retry:
                break


# Perform backup function prior to sync
def make_backup_copy(original_folder):
    backup_folder = original_folder + ".bak"
    while True:
        try:
            if check_permissions(backup_folder, 'backup folder', "write") and check_permissions(original_folder, 'original folder', "read"):
                if os.path.exists(backup_folder):
                    shutil.rmtree(backup_folder)

                shutil.copytree(original_folder, backup_folder)

                comparison = filecmp.dircmp(original_folder, backup_folder)

                if comparison.left_list == comparison.right_list and not comparison.diff_files and not comparison.common_funny:
                    match, mismatch, errors = filecmp.cmpfiles(original_folder, backup_folder, comparison.common_files)
                    if len(mismatch) == 0 and len(errors) == 0:
                        break
                else:
                    raise Exception("Mismatch in directory contents")
        except Exception as e:
            reply = QMessageBox.warning(None, "Backup Error",
                                        f"There was an error making a backup copy: {str(e)}. "
                                        "Please verify the source and destination folders, and try again.",
                                        QMessageBox.Retry | QMessageBox.Abort, QMessageBox.Retry)
            if reply != QMessageBox.Retry:
                break


# REFACTORED FUNCTION: Function to check and sync saves
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
    checkout_previous_user = io_savetitan_file(cloud_profile_folder, "read", profile_id, "checkout")
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
            io_savetitan_file(profile_info_savetitan_path, "write", profile_id, "checkout", checkout_current_user)

    elif not checkout_previous_user:
        io_savetitan_file(profile_info_savetitan_path, "write", profile_id, "checkout", checkout_current_user)

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
                launch_game_without_sync(game_executable)
                io_savetitan_file(profile_info_savetitan_path, "write", profile_id, "checkout", None)
                sync_diag.accept()
            
            def on_rejected_connect():
                io_savetitan_file(profile_info_savetitan_path, "write", profile_id, "checkout", None)
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

        io_savetitan_file(profile_info_savetitan_path, "write", profile_id, "checkout", None)

    QTimer.singleShot(0, launch_game_dialog)


# REFACTORED FUNCTION: Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-runid", help="Specify the profile ID to be used")
args = parser.parse_args()

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

app = QApplication([])

cloud_storage_path = io_config_file("global_file", "read", None, "cloud_storage_path")

if args.runid:
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
    #show_config_dialog(config)
    app.exec_()
    
app.exec_()