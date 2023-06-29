import os
import sys
import filecmp
from datetime import datetime
import socket
import subprocess
import psutil
import time

from pathlib import Path

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5 import uic

from modules.io import check_permissions
from modules.io import io_profile
from modules.io import io_global
from modules.io import io_go
from modules.io import io_savetitan
from modules.io import copy_save_to_cloud
from modules.io import copy_save_to_local
from modules.io import send_notification
from modules.io import debug_msg

import modules.paths as paths
script_dir = paths.script_dir
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file
game_overrides_config_file = paths.game_overrides_config_file
python_exe_path = paths.python_exe_path


# Function to check and sync saves
def check_and_sync_saves(profile_id, launch_game_bool=True):
    #Load data set
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_fields = io_profile("read", profile_id, "profile")

    platform_flag = 1 if sys.platform == 'win32' else None
 
    profile_name = profile_fields.get("name")
    game_executable = profile_fields.get("game_executable")
    local_save_folder = profile_fields.get("local_save_folder")
    save_slot = profile_fields.get("save_slot")
    sync_mode = profile_fields.get("sync_mode")

    # Read omitted files
    omitted_files = io_profile("read", profile_id, "overrides", "omitted") or []

    cloud_profile_save_path = os.path.join(cloud_storage_path, profile_id, "save" + save_slot)

    if sync_mode != "Sync":
        if launch_game_bool:
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
            f"Do you want to continue?"
        )
        yes_button = checkout_msgbox.addButton(QMessageBox.Yes)
        no_button = checkout_msgbox.addButton(QMessageBox.No)
        checkout_msgbox.setDefaultButton(no_button)
        result = checkout_msgbox.exec_()

        if result == -1 or checkout_msgbox.clickedButton() == no_button:
            if launch_game_bool:
                sys.exit()
            else:
                return
        elif checkout_msgbox.clickedButton() == yes_button:
            io_savetitan("write", profile_id, "profile", "checkout", checkout_current_user)

    elif not checkout_previous_user:
        io_savetitan("write", profile_id, "profile", "checkout", checkout_current_user)

    if os.path.exists(cloud_profile_save_path) and os.listdir(cloud_profile_save_path):
        files_identical = True
        for dirpath, dirnames, filenames in os.walk(local_save_folder):
            for filename in filenames:
                local_file = os.path.join(dirpath, filename)

                # Check: Skip omitted files
                rel_file_path = os.path.relpath(local_file, local_save_folder)

                if rel_file_path in omitted_files:
                    continue

                cloud_file = os.path.join(cloud_profile_save_path, os.path.relpath(local_file, local_save_folder))
                if os.path.exists(cloud_file):
                    rel_cloud_file_path = os.path.relpath(cloud_file, cloud_profile_save_path)

                    if rel_cloud_file_path in omitted_files:
                        continue
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
                if launch_game_bool:
                    send_notification(f"Save is up to date. Launching \"{profile_name}\".")
                    launch_game(profile_id)
                else:
                    send_notification(f"Save is up to date for \"{profile_name}\". No changes made.")
                
            # Result: More cloud files than local - Action: Copy contents of cloud folder to local
            elif cloud_files_count > local_files_count:
                copy_save_to_local(profile_id)
                if launch_game_bool:
                    send_notification(f"Save is up to date. Launching \"{profile_name}\".")
                    launch_game(profile_id)
                else:
                    send_notification(f"Save is up to date for \"{profile_name}\". No changes made.")
                
            # Result: Content and amount of files is identical - Action: Launch the game, upload when done
            else:
                if launch_game_bool:
                    send_notification(f"Save is up to date. Launching \"{profile_name}\".")
                    launch_game(profile_id)
                else:
                    send_notification(f"Save is up to date for \"{profile_name}\". No changes made.")

        # Result: Files aren't identical - Action: Compare files to find latest timestamp
        else:
            local_file_time = datetime(1900, 1, 1)
            cloud_file_time = datetime(1900, 1, 1)

            for dirpath, dirnames, filenames in os.walk(local_save_folder):
                for filename in filenames:
                    local_file = os.path.join(dirpath, filename)

                    # Check: Skip omitted files
                    rel_file_path = os.path.relpath(local_file, local_save_folder)

                    if rel_file_path in omitted_files:
                        continue

                    file_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filename)))
                    if local_file_time < file_time:
                        local_file_time = file_time
                           
            for dirpath, dirnames, filenames in os.walk(cloud_profile_save_path):
                for filename in filenames:
                    cloud_file = os.path.join(dirpath, filename)

                    cloud_file_norm = os.path.normpath(str(Path(cloud_file)))
                    if cloud_file_norm in omitted_files:
                        continue
                    
                    file_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filename)))
                    if cloud_file_time < file_time:
                        cloud_file_time = file_time
                           
            for dirpath, dirnames, filenames in os.walk(cloud_profile_save_path):
                for filename in filenames:
                    file_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filename)))
                    if cloud_file_time < file_time:
                        cloud_file_time = file_time

            local_save_time_str = local_file_time.strftime("%B %d, %Y, %I:%M:%S %p")
            cloud_save_time_str = cloud_file_time.strftime("%B %d, %Y, %I:%M:%S %p")

            sync_diag = uic.loadUi("ui/sync_diag.ui")
            sync_diag.local_date.setText(local_save_time_str)
            sync_diag.cloud_date.setText(cloud_save_time_str)

            config_profiles = io_profile("read", profile_id, "profile")

            sync_diag.setWindowTitle(f"Profile: {profile_name}")
            if cloud_file_time > local_file_time:
                sync_diag.local_indication.setText("Local Copy: Older")
                sync_diag.cloud_indication.setText("Cloud Copy: Newer")
            else:
                sync_diag.local_indication.setText("Local Copy: Newer")
                sync_diag.cloud_indication.setText("Cloud Copy: Older")


            def on_nosyncButton_clicked():
                executable_path = io_profile("read", profile_id, "profile", "game_executable")
                io_savetitan("write", profile_id, "profile", "checkout")
                sync_diag.hide
                if launch_game_bool:
                    launch_game_without_sync(executable_path)


            def on_rejected_connect():
                io_savetitan("write", profile_id, "profile", "checkout")
                if launch_game_bool:
                    sys.exit()
                else:
                    return


            def handle_upload_button_click():
                sync_diag.hide()
                
                if launch_game_bool:
                    launch_game(profile_id)
                else:
                    result = copy_save_to_cloud(profile_id)
                    profile_fields = io_profile("read", profile_id, "profile")
                    profile_name = profile_fields.get("name")

                    if result is None:
                        debug_msg("Cloud sync successful.")
                        send_notification(f"Profile \"{profile_name}\" has synced to the cloud successfully.")
                    else:
                        debug_msg(f"Cloud sync failed: {result}")
                        send_notification(f"Profile \"{profile_name}\" has failed to sync to the cloud: {result}")


            def handle_download_button_click():
                sync_diag.hide()
                result = copy_save_to_local(profile_id)
                
                if launch_game_bool:
                    launch_game(profile_id)
                else:
                    profile_fields = io_profile("read", profile_id, "profile")
                    profile_name = profile_fields.get("name")

                    if result is None:
                        debug_msg("Local sync successful.")
                        send_notification(f"Profile \"{profile_name}\" has synced the cloud save to local successfully.")
                    else:
                        debug_msg(f"Local sync failed: {result}")
                        send_notification(f"Profile \"{profile_name}\" has failed to sync the cloud save to local: {result}")

            sync_diag.downloadButton.clicked.connect(handle_download_button_click)
            sync_diag.uploadButton.clicked.connect(handle_upload_button_click)
            sync_diag.nosyncButton.clicked.connect(lambda: [on_nosyncButton_clicked()])
            sync_diag.rejected.connect(lambda: on_rejected_connect())
            
            sync_diag.exec_()
    else:
        if launch_game_bool:
            launch_game(profile_id)
        else:
            send_notification(f"Save is up to date for \"{profile_name}\". No changes made.")
            return


# Function to wait for a process and its children to finish
def wait_for_process_to_finish(process_names):
    if not isinstance(process_names, list):
        process_names = [process_names]

    while True:
        matching_processes = [proc for proc in psutil.process_iter(['name', 'pid', 'status']) 
                              if proc.info['name'].lower() in map(str.lower, process_names) 
                              and proc.info['status'] != 'zombie']

        if not matching_processes:
            debug_msg(f"No matching processes found for: {process_names}")
            time.sleep(2)

            matching_processes = [proc for proc in psutil.process_iter(['name', 'pid', 'status']) 
                                  if proc.info['name'].lower() in map(str.lower, process_names)
                                  and proc.info['status'] != 'zombie']

            if not matching_processes:
                debug_msg('Processes have finished.')
                return True
            else:
                debug_msg(f'Processes restarted with PID {matching_processes[0].info["pid"]}. Restarting tracking.')
        else:
            debug_msg(f'Matching processes still running: {matching_processes}')

        time.sleep(2)


def launch_game(profile_id):
    debug_msg("Launching game...")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    profile_data = io_profile("read", profile_id, "profile")
    profile_name = profile_data.get("name")
    game_executable = profile_data.get("game_executable")

    debug_msg(f"Profile name: {profile_name}, Game executable: {game_executable}")

    game_filename = os.path.basename(game_executable)
    process_names = io_go("read", game_filename, "process_name")
    process_names = [game_filename] + (process_names if process_names else [])

    debug_msg(f"Process names: {process_names}")

    if not check_permissions(game_executable, 'game executable', "execute"):
        return

    game_process = subprocess.Popen(game_executable)

    debug_msg("Game process started.")
    
    if io_go("read", game_filename, "process_tracking") == False:
        debug_msg("Process tracking disabled. Opening upload dialog.")
        upload_dialog(profile_id)
        sys.exit()

    if wait_for_process_to_finish(process_names):
        debug_msg("Game process has finished.")

        def upload_and_exit():
            debug_msg("Starting cloud sync...")
            result = copy_save_to_cloud(profile_id)

            if result == None:
                debug_msg("Cloud sync successful.")
                send_notification(f"Profile \"{profile_name}\" has synced to the cloud successfully.")
            else:
                debug_msg(f"Cloud sync failed: {result}")
                send_notification(f"Profile \"{profile_name}\" has failed to sync to the cloud: {result}")
            
            io_savetitan("write", profile_id, "profile", "checkout")
            sys.exit()

        QTimer.singleShot(0, upload_and_exit)


def upload_dialog(profile_id):
    message_box = QMessageBox()
    message_box.setWindowTitle("Game in Progress")
    message_box.setText("Please click 'Upload to Cloud' when you have finished playing.")
    
    done_button = message_box.addButton("Upload to Cloud", QMessageBox.AcceptRole)
    abort_button = message_box.addButton("Abort Sync", QMessageBox.RejectRole)
    
    message_box.exec_()

    if message_box.clickedButton() == done_button:
        copy_save_to_cloud(profile_id)

    io_savetitan("write", profile_id, "profile", "checkout")


# Function to launch the game without sync
def launch_game_without_sync(executable_path):
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    
    if not check_permissions(executable_path, 'game executable', "execute"):
        return

    subprocess.Popen(executable_path)
    
    sys.exit()