import os
import sys
import glob
import configparser

from configparser import ConfigParser
from PyQt5.QtWidgets import QMessageBox

import modules.paths as paths

profiles_config_file = paths.profiles_config_file
global_config_file = paths.global_config_file


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
            if not os.path.exists(config_file) or not check_permissions(config_file, "file", "read"):
                return None
            config = ConfigParser()
            config.read(config_file)
            if config.has_option(section, field):
                return config.get(section, field)
            else:
                return None

        elif profile_id and section:
            config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
            if not os.path.exists(config_file) or not check_permissions(config_file, "file", "read"):
                return None
            config = ConfigParser()
            config.read(config_file)
            if config.has_section(section):
                return dict(config.items(section))
            else:
                return None

        elif section and field and value:
            matching_profiles = []
            for file in glob.glob(os.path.join(profiles_config_file, '*.ini')):
                if not check_permissions(file, "file", "read"):
                    continue
                config = ConfigParser()
                config.read(file)
                file_id = os.path.splitext(os.path.basename(file))[0]
                if config.has_option(section, field) and config.get(section, field).lower() == value.lower():
                    matching_profiles.append(file_id)
            return matching_profiles

        elif section:
            profiles_data = {}
            for file in glob.glob(os.path.join(profiles_config_file, '*.ini')):
                if not check_permissions(file, "file", "read"):
                    continue
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
        
        os.makedirs(profiles_config_file, exist_ok=True)
        
        config_file = os.path.join(profiles_config_file, f"{profile_id}.ini")
        config = ConfigParser()

        if os.path.exists(config_file):
            if not check_permissions(config_file, "file", "write"):
                raise PermissionError(f"Write permission denied for the file: {config_file}")
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
            if not check_permissions(config_file, "file", "write"): # Permission to delete a file is considered as write permission
                raise PermissionError(f"Delete permission denied for the file: {config_file}")
            os.remove(config_file)
        else:
            raise FileNotFoundError(f"No profile found with ID: {profile_id}")

 
def io_global(read_write_mode, section=None, field=None, value=None):
    read_write_mode = str(read_write_mode)
    section = str(section) if section is not None else None
    field = str(field) if field is not None else None
    value = str(value) if value is not None else None
    config = ConfigParser()
    config.read(global_config_file)

    if read_write_mode == "read":
        if not section or not field:
            raise ValueError("For 'read' mode, section and field must be specified.")
        if config.has_option(section, field):
            return config.get(section, field)
        else:
            return None
        
    elif read_write_mode == "write":
        if not section or not field:
            raise ValueError("For 'write' mode, section and field must be specified.")
        
        os.makedirs(os.path.dirname(global_config_file), exist_ok=True)

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
    
    elif read_write_mode == "delete":
        if not field:
            raise ValueError("For delete operation, field is required.")
        
        if config.has_option(section, field):
            config.remove_option(section, field)
        
            with open(profile_info_path, 'w') as configfile:
                config.write(configfile)
        else:
            raise ValueError(f"No such field '{field}' in section '{section}'.")
    else:
        raise ValueError("Invalid operation. Expected 'read', 'write' or 'delete'.")