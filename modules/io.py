import os
import glob
import string
import random
import filecmp
import shutil
import json
import logging

from datetime import datetime
from pathlib import Path
from filecmp import cmp
from PyQt5.QtWidgets import QMessageBox

import modules.paths as paths
script_dir = paths.script_dir
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file
game_overrides_config_file = paths.game_overrides_config_file
python_exe_path = paths.python_exe_path

logger = logging.getLogger('debug_logger')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('debug.log')
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


# Generate a 6 character string for use for profile_id's
def generate_id():
    characters = string.ascii_lowercase + string.digits
    id_length = 6
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

    #cloud_storage_path = cloud_storage_path.replace("\\", "\\\\")

    if check_permissions(cloud_storage_path, 'cloud storage', "read"):
        return True
    else:
        QMessageBox.critical(None, "Network Error",
                             f"An error occurred while trying to access the network share: Permission denied.")
        return False


def io_profile(read_write_mode, profile_id=None, section=None, field=None, value=None, modifier=None):
    read_write_mode = str(read_write_mode)
    profile_id = str(profile_id) if profile_id is not None else None
    section = str(section) if section is not None else None
    field = str(field) if field is not None else None

    original_value = value
    if isinstance(value, str):
        if modifier == "remove":
            value = value.lower()

    modifier = str(modifier) if modifier is not None else None

    if read_write_mode == "read":

        if profile_id and section and field:
            json_file = os.path.join(user_config_file, "profiles", f"{profile_id}.json")

            if not os.path.exists(json_file) or not check_permissions(json_file, "file", "read"):
                return None

            with open(json_file, 'r') as f:
                data = json.load(f)

            return data.get(section, {}).get(field, None)

        elif profile_id and section:
            json_file = os.path.join(user_config_file, "profiles", f"{profile_id}.json")
            if not os.path.exists(json_file) or not check_permissions(json_file, "file", "read"):
                return None
            with open(json_file, 'r') as f:
                data = json.load(f)
            return data.get(section, None)

        elif section and field and value:
            matching_profiles = []
            for file in glob.glob(os.path.join(user_config_file, "profiles", '*.json')):
                if not check_permissions(file, "file", "read"):
                    continue
                with open(file, 'r') as f:
                    data = json.load(f)
                file_id = os.path.splitext(os.path.basename(file))[0]
                if data.get(section, {}).get(field, "").lower() == value.lower():
                    matching_profiles.append(file_id)
            return matching_profiles

        elif section:
            profiles_data = {}
            for file in glob.glob(os.path.join(user_config_file, "profiles", '*.json')):
                if not check_permissions(file, "file", "read"):
                    continue
                with open(file, 'r') as f:
                    data = json.load(f)
                file_id = os.path.splitext(os.path.basename(file))[0]
                if section in data:
                    profiles_data[file_id] = data[section]
            return profiles_data
        else:
            return [os.path.splitext(os.path.basename(file))[0] for file in glob.glob(os.path.join(user_config_file, "profiles", '*.json'))]

    elif read_write_mode == "write":
        if not profile_id or not section or not field:
            raise ValueError("For 'write' mode, profile_id, section, and field must be specified.")
        
        os.makedirs(os.path.join(user_config_file, "profiles"), exist_ok=True)
        
        json_file = os.path.join(user_config_file, "profiles", f"{profile_id}.json")

        data = {}
        if os.path.exists(json_file):
            if not check_permissions(json_file, "file", "write"):
                raise PermissionError(f"Write permission denied for the file: {json_file}")
            with open(json_file, 'r') as f:
                data = json.load(f)

        if section not in data:
            data[section] = {}

        current_value = data[section].get(field, "")

        if modifier == "add":
            if not isinstance(current_value, list):
                current_value = [current_value] if current_value else []
            current_value.append(value)
        elif modifier == "remove":
            if isinstance(current_value, list):
                if value in map(str.lower, current_value):
                    current_value.remove(next(item for item in current_value if item.lower() == value))
            elif not isinstance(current_value, list) and current_value.lower() == value:
                current_value = None
        else:
            current_value = value if value is not None else ""

        data[section][field] = current_value
        with open(json_file, "w") as f:
            json.dump(data, f)

    elif read_write_mode == "delete":
        if not profile_id:
            raise ValueError("For 'delete' mode, profile_id must be specified.")

        json_file = os.path.join(user_config_file, "profiles", f"{profile_id}.json")
        if os.path.exists(json_file):
            if not check_permissions(json_file, "file", "write"):
                raise PermissionError(f"Delete permission denied for the file: {json_file}")
            os.remove(json_file)
        else:
            raise FileNotFoundError(f"No profile found with ID: {profile_id}")


def io_config(read_write_mode, config_file, section=None, field=None, value=None, modifier=None):
    read_write_mode = str(read_write_mode).lower()
    section = str(section) if section is not None else None
    field = str(field) if field is not None else None

    original_value = value
    if isinstance(value, str):
        if modifier == "remove":
            value = value.lower()
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False

    modifier = str(modifier).lower() if modifier is not None else None

    data = {}
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            data = json.load(f)
    else:
        print(f"File {config_file} does not exist. Data is empty.")

    if read_write_mode == "read":
        if not section or not field:
            raise ValueError("For 'read' mode, section and field must be specified.")
        return data.get(section, {}).get(field, None)

    elif read_write_mode == "write":
        if not section or not field:
            raise ValueError("For 'write' mode, section and field must be specified.")

        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        if section not in data:
            data[section] = {}

        current_value = data[section].get(field, "")

        if modifier == "add":
            if not isinstance(current_value, list):
                current_value = [current_value] if current_value else []
            if original_value not in current_value:
                current_value.append(original_value)
        elif modifier == "remove":
            if isinstance(current_value, list):
                if value in map(str.lower, current_value):
                    current_value.remove(next(item for item in current_value if item.lower() == value))
            elif not isinstance(current_value, list) and str(current_value).lower() == value:
                current_value = None
        else:
            current_value = value if value is not None else ""

        data[section][field] = current_value
        with open(config_file, "w") as f:
            json.dump(data, f)

    else:
        raise ValueError("Invalid mode. Expected 'read' or 'write'.")


def io_global(read_write_mode, section=None, field=None, value=None, modifier=None):
    return io_config(read_write_mode, global_config_file, section, field, value, modifier)


def io_go(read_write_mode, section=None, field=None, value=None, modifier=None):
    return io_config(read_write_mode, game_overrides_config_file, section, field, value, modifier)


def io_savetitan(read_write_mode, profile_id, section, field=None, write_value=None, modifier=None):
    profile_id = str(profile_id)
    section = str(section)
    if field is not None:
        field = str(field)
    if write_value is not None:
        write_value = str(write_value)
    if modifier is not None:
        modifier = str(modifier)

    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    if cloud_storage_path is None:
        raise ValueError("Cloud storage path is not defined.")
        
    profile_info_path = os.path.join(cloud_storage_path, profile_id, "profile_info.savetitan")

    data = {}
    if os.path.exists(profile_info_path):
        with open(profile_info_path, 'r') as f:
            data = json.load(f)

    if read_write_mode == "read":
        if field:
            return data.get(section, {}).get(field, None)
        else:
            return data.get(section, None)

    elif read_write_mode == "write":
        if not field:
            raise ValueError("For write operation, field is required.")

        if section not in data:
            data[section] = {}

        current_value = data[section].get(field, "")

        if modifier == "add":
            if not isinstance(current_value, list):
                current_value = [current_value] if current_value else []
            current_value.append(write_value)
        elif modifier == "remove":
            if isinstance(current_value, list) and write_value in current_value:
                current_value.remove(write_value)
            elif not isinstance(current_value, list) and current_value == write_value:
                current_value = None
        else:
            current_value = write_value if write_value is not None else ""

        data[section][field] = current_value

        with open(profile_info_path, 'w') as f:
            json.dump(data, f)
    
    elif read_write_mode == "delete":
        if not field:
            raise ValueError("For delete operation, field is required.")

        if section in data and field in data[section]:
            del data[section][field]
            with open(profile_info_path, 'w') as f:
                json.dump(data, f)
        else:
            raise ValueError(f"No such field '{field}' in section '{section}'.")
            
    else:
        raise ValueError("Invalid operation. Expected 'read', 'write' or 'delete'.")


# Checks for file mismatch (Unused currently due to issues)
def check_folder_mismatch(folder_a, folder_b, profile_id):
    comparison = filecmp.dircmp(folder_a, folder_b)

    omitted_files = io_profile("read", profile_id, "overrides", "omitted").split(',')
    omitted_files = [str(Path(file)) for file in omitted_files]

    def compare_dirs(comp):
        filtered_diff_files = [file for file in comp.diff_files if file not in omitted_files]
        filtered_left_only = [file for file in comp.left_only if file not in omitted_files]
        filtered_right_only = [file for file in comp.right_only if file not in omitted_files]
        filtered_funny_files = [file for file in comp.funny_files if file not in omitted_files]
        
        if filtered_diff_files:
            print(f"Differing files: {filtered_diff_files}")
        if filtered_left_only:
            print(f"Files only in left directory: {filtered_left_only}")
        if filtered_right_only:
            print(f"Files only in right directory: {filtered_right_only}")
        if filtered_funny_files:
            print(f"Funny files: {filtered_funny_files}")

        if filtered_diff_files or filtered_left_only or filtered_right_only or filtered_funny_files:
            return True

        match, mismatch, errors = filecmp.cmpfiles(comp.left, comp.right, comp.common_files, shallow=False)
        if mismatch or errors:
            print(f"Mismatched files: {mismatch}")
            print(f"Errored files: {errors}")

        if mismatch or errors:
            return True

        for subcomp in comp.subdirs.values():
            if compare_dirs(subcomp):
                return True

        return False

    return compare_dirs(comparison)


# Function to sync saves (Copy local saves to cloud storage)
def copy_save_to_cloud(profile_id):
    debug_msg("Starting cloud sync...")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_data = io_profile("read", profile_id, "profile")
    local_save_folder = profile_data.get("local_save_folder")
    save_slot = profile_data.get("save_slot")
    
    omitted_files = io_profile("read", profile_id, "overrides", "omitted") or []

    debug_msg(f"Local save folder: {local_save_folder}, Save slot: {save_slot}")

    cloud_profile_save_path = Path(cloud_storage_path) / profile_id / f"save{save_slot}"

    if not network_share_accessible():
        return "Cloud path is inaccessible"

    debug_msg("Cloud path is accessible. Making backup copy...")
    #make_backup_copy(profile_id, "cloud_backup")

    for root, dirs, files in os.walk(local_save_folder):
        for file in files:
            local_file = os.path.join(root, file)
            rel_path = os.path.relpath(local_file, local_save_folder)
            cloud_file = os.path.join(cloud_profile_save_path, rel_path)

            if rel_path in omitted_files:
                debug_msg(f"Skipping file because it's omitted: {local_file}")
                continue

            if not os.path.exists(cloud_file) or not filecmp.cmp(local_file, cloud_file, shallow=False):
                debug_msg(f"Copying or overwriting file: {local_file} to {cloud_file}")
                os.makedirs(os.path.dirname(cloud_file), exist_ok=True)
                shutil.copy2(local_file, cloud_file)

    for root, dirs, files in os.walk(cloud_profile_save_path, topdown=False):
        for name in files:
            cloud_file = os.path.join(root, name)
            rel_path = os.path.relpath(cloud_file, cloud_profile_save_path)
            local_file = os.path.join(local_save_folder, rel_path)

            if not os.path.exists(local_file):
                debug_msg(f"Deleting file: {cloud_file}")
                os.remove(cloud_file)

        for name in dirs:
            cloud_dir = os.path.join(root, name)
            rel_path = os.path.relpath(cloud_dir, cloud_profile_save_path)
            local_dir = os.path.join(local_save_folder, rel_path)

            if not os.path.exists(local_dir):
                debug_msg(f"Deleting directory: {cloud_dir}")
                shutil.rmtree(cloud_dir)

    debug_msg(f"Sync for Profile ID: {profile_id} to cloud completed successfully.")
    return


# Function to sync saves (Copy cloud saves to local storage)
def copy_save_to_local(profile_id):
    debug_msg("Starting local sync...")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_data = io_profile("read", profile_id, "profile")
    local_save_folder = profile_data.get("local_save_folder")
    save_slot = profile_data.get("save_slot")
    
    omitted_files = io_profile("read", profile_id, "overrides", "omitted") or []

    debug_msg(f"Local save folder: {local_save_folder}, Save slot: {save_slot}")

    cloud_profile_save_path = Path(cloud_storage_path) / profile_id / f"save{save_slot}"

    if not network_share_accessible():
        return "Cloud path is inaccessible"

    debug_msg("Cloud path is accessible. Making backup copy...")
    #make_backup_copy(profile_id, "local_backup")

    for root, dirs, files in os.walk(cloud_profile_save_path):
        for file in files:
            cloud_file = os.path.join(root, file)
            rel_path = os.path.relpath(cloud_file, cloud_profile_save_path)
            local_file = os.path.join(local_save_folder, rel_path)

            if rel_path in omitted_files:
                debug_msg(f"Skipping file because it's omitted: {cloud_file}")
                continue

            if not os.path.exists(local_file) or not filecmp.cmp(local_file, cloud_file, shallow=False):
                debug_msg(f"Copying or overwriting file: {cloud_file} to {local_file}")
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                shutil.copy2(cloud_file, local_file)

    for root, dirs, files in os.walk(local_save_folder, topdown=False):
        for name in files:
            local_file = os.path.join(root, name)
            rel_path = os.path.relpath(local_file, local_save_folder)
            cloud_file = os.path.join(cloud_profile_save_path, rel_path)

            if not os.path.exists(cloud_file):
                debug_msg(f"Deleting file: {local_file}")
                os.remove(local_file)

        for name in dirs:
            local_dir = os.path.join(root, name)
            rel_path = os.path.relpath(local_dir, local_save_folder)
            cloud_dir = os.path.join(cloud_profile_save_path, rel_path)

            if not os.path.exists(cloud_dir):
                debug_msg(f"Deleting directory: {local_dir}")
                shutil.rmtree(local_dir)

    debug_msg(f"Sync for Profile ID: {profile_id} to local completed successfully.")
    return


# Perform backup function prior to sync
def make_backup_copy(profile_id, which_side):
    debug_msg("Starting backup process...")
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    save_slot = io_profile("read", profile_id, "profile", "save_slot")
    cloud_profile_folder_save = os.path.join(cloud_storage_path, profile_id, f"save{save_slot}")
    cloud_profile_folder_save_bak = f"{cloud_profile_folder_save}.bak"

    if which_side not in ["local_backup", "cloud_backup"]:
        raise Exception("Invalid which_side argument")

    if os.path.exists(cloud_profile_folder_save_bak):
        debug_msg(f"Deleting existing backup: {cloud_profile_folder_save_bak}")
        shutil.rmtree(cloud_profile_folder_save_bak)

    os.makedirs(cloud_profile_folder_save_bak, exist_ok=True)

    if which_side == "local_backup":
        local_save_folder = io_profile("read", profile_id, "profile", "local_save_folder")
        debug_msg("Performing local backup...")
        for root, dirs, files in os.walk(local_save_folder):
            rel_path = os.path.relpath(root, local_save_folder)
            backup_path = os.path.join(cloud_profile_folder_save_bak, rel_path)

            for file in files:
                local_file = os.path.join(root, file)
                backup_file = os.path.join(backup_path, file)

                debug_msg(f"Copying file: {local_file} to {backup_file}")
                os.makedirs(backup_path, exist_ok=True)
                shutil.copy2(local_file, backup_file)

    elif which_side == "cloud_backup":
        debug_msg("Performing cloud backup...")
        for root, dirs, files in os.walk(cloud_profile_folder_save):
            rel_path = os.path.relpath(root, cloud_profile_folder_save)
            backup_path = os.path.join(cloud_profile_folder_save_bak, rel_path)

            for file in files:
                cloud_file = os.path.join(root, file)
                backup_file = os.path.join(backup_path, file)

                debug_msg(f"Copying file: {cloud_file} to {backup_file}")
                os.makedirs(backup_path, exist_ok=True)
                shutil.copy2(cloud_file, backup_file)
    
    debug_msg("Backup process completed.")


def send_notification(message):
    import sys
    if sys.platform == "win32":
        from plyer import notification
        notification.notify(title="SaveTitan", message=message)
    elif sys.platform == "darwin":
        from pync import Notifier
        Notifier.notify(message, title="SaveTitan")
    elif sys.platform.startswith("linux"):
        import notify2
        notify2.init("SaveTitan")
        notification = notify2.Notification("SaveTitan", message)
        notification.show()


def debug_msg(message):
    if io_global("read", "config", "debug") == "enable":
        logger.debug(message)