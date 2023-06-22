import os
import glob
import string
import random
import filecmp
import shutil
import json

from pathlib import Path

from PyQt5.QtWidgets import QMessageBox

import modules.paths as paths
script_dir = paths.script_dir
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file
game_overrides_config_file = paths.game_overrides_config_file


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
    value = str(value) if value is not None else None
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
            if isinstance(current_value, list) and value in current_value:
                current_value.remove(value)
            elif not isinstance(current_value, list) and current_value == value:
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

    original_value = value  # Keep the original value
    if isinstance(value, str):
        value = value.lower()
        if value == 'true':
            value = True
        elif value == 'false':
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
                current_value = [item for item in current_value if str(item).lower() != value]
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


# Custom function to copy directory with ability to skip certain files
def copytree_custom(src, dst, ignore_list=None):
    if ignore_list is None:
        ignore_list = []

    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree_custom(s, d, ignore_list)
        else:
            if str(Path(s)) not in ignore_list:
                shutil.copy2(s, d)


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


# Function to sync saves (Copy cloud saves to local storage)
def copy_save_to_cloud(profile_id):
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_data = io_profile("read", profile_id, "profile")
    local_save_folder = profile_data.get("local_save_folder")
    save_slot = profile_data.get("save_slot")

    omitted_files_str = io_profile("read", profile_id, "overrides", "omitted") or ""
    omitted_files = [os.path.normpath(f.strip()) for f in omitted_files_str.split(",") if f.strip()]

    cloud_profile_save_path = Path(cloud_storage_path) / profile_id / f"save{save_slot}"

    if not network_share_accessible():
        return "Cloud path is inaccessible"
    
    make_backup_copy(profile_id, "cloud_backup")

    for root, dirs, files in os.walk(local_save_folder):
        for file in files:
            file_path = Path(root) / file
            normalized_file_path = os.path.normpath(str(file_path))

            if normalized_file_path in omitted_files:
                continue

            rel_path = file_path.relative_to(local_save_folder)
            dest_path = cloud_profile_save_path / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                dest_path.unlink()
            
            shutil.copy2(file_path, dest_path)

    print(f"Sync for Profile ID: {profile_id} to cloud completed successfully.")
    return


# Function to sync saves (Copy cloud saves to local storage)
def copy_save_to_local(profile_id):
    cloud_storage_path = io_global("read", "config", "cloud_storage_path")

    profile_data = io_profile("read", profile_id, "profile")
    local_save_folder = profile_data.get("local_save_folder")
    save_slot = profile_data.get("save_slot")

    cloud_profile_save_path = Path(cloud_storage_path) / profile_id / f"save{save_slot}"

    omitted_files_str = io_profile("read", profile_id, "overrides", "omitted") or ""
    omitted_files = [os.path.normpath(f.strip()) for f in omitted_files_str.split(",") if f.strip()]

    if not network_share_accessible():
        return

    make_backup_copy(profile_id, "local_backup")

    for root, dirs, files in os.walk(cloud_profile_save_path):
        for file in files:
            file_path = Path(root) / file

            rel_path = file_path.relative_to(cloud_profile_save_path)
            dest_path = Path(local_save_folder) / rel_path
            normalized_dest_path = os.path.normpath(str(dest_path))

            if normalized_dest_path in omitted_files:
                continue

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                dest_path.unlink()
            
            shutil.copy2(file_path, dest_path)

    print(f"Sync for Profile ID: {profile_id} to local save directory completed successfully.")


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