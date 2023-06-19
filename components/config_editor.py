import os
import configparser
import json
import shutil
import re

from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, QSortFilterProxyModel, QRegExp

from modules.io import io_profile

#from modules.misc import center_dialog_over_dialog

import modules.paths as paths
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file


class ConfigEditorDialog(QDialog):
    def __init__(self, profile_id, parent=None):
        super().__init__(parent)

        self.initial_data = {}

        self.ui = uic.loadUi("ui/config_editor.ui", self)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

        self.profile_id = profile_id
        
        self.file_formats = {}

        self.file_combo_box = self.ui.file_comboBox
        self.section_combo_box = self.ui.section_comboBox
        self.filter_edit_box = self.ui.filter_lineEdit
        self.editor_table_view = self.ui.editor_tableView

        self.save_button = self.ui.save_pushButton
        self.close_button = self.ui.close_pushButton
        self.revert_button = self.ui.revert_pushButton
        self.reset_button = self.ui.reset_pushButton
        self.addfolders_button = self.ui.addfolders_pushButton

        self.reset_pushButton.clicked.connect(self.reset_changes)
        self.save_button.clicked.connect(self.save_changes)
        self.close_button.clicked.connect(lambda: self.accept())
        self.revert_button.clicked.connect(self.restore_backup)
        self.addfolders_button.clicked.connect(self.config_editor_add_folders_dialog)

        self.populate_file_combo_box()
        self.populate_section_combo_box()

        self.table_model = QStandardItemModel()
        self.table_model.dataChanged.connect(self.handle_item_changed)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.editor_table_view.setModel(self.proxy_model)
        self.editor_table_view.verticalHeader().setVisible(False)

        self.file_combo_box.currentIndexChanged.connect(self.populate_section_combo_box)
        self.section_combo_box.currentIndexChanged.connect(self.populate_table_view)

        self.filter_edit_box.textChanged.connect(self.update_filter)

        self.populate_table_view()


    def config_editor_add_folders_dialog(self):
        config_editor_add_folders_dialog = uic.loadUi("ui/list_dialog.ui")
        config_editor_add_folders_dialog.setWindowFlags(config_editor_add_folders_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        config_editor_add_folders_dialog.setFixedSize(config_editor_add_folders_dialog.size())

        config_editor_add_folders_dialog.setWindowTitle("SaveTitan - Modify Monitored Config Folders")

        #center_dialog_over_dialog(ConfigEditorDialog, config_editor_add_folders_dialog)

        config_editor_add_folders_dialog.listWidget.setEnabled(False)

        profile_data = io_profile("read", self.profile_id, "profile")
        watched_config_folders = profile_data.get("watched_config_folders", [])

        for folder_path in watched_config_folders:
            config_editor_add_folders_dialog.listWidget.addItem(folder_path)

        if len(watched_config_folders) > 0:
            config_editor_add_folders_dialog.listWidget.setEnabled(True)

        def add_folder():
            folder_dialog = QFileDialog()
            folder_path = folder_dialog.getExistingDirectory()

            if folder_path:
                folder_path = os.path.normpath(os.path.abspath(folder_path))
                io_profile("write", self.profile_id, "profile", "watched_config_folders", folder_path, "add")
                config_editor_add_folders_dialog.listWidget.setEnabled(True)
                config_editor_add_folders_dialog.listWidget.addItem(folder_path)

        def remove_folder():
            selected_item = config_editor_add_folders_dialog.listWidget.currentItem()

            if selected_item:
                confirm_msg = QMessageBox.question(None, "Confirmation", "Do you want to remove the folder from watched config folders?", QMessageBox.Yes | QMessageBox.No)
                
                if confirm_msg == QMessageBox.Yes:
                    selected_folder = selected_item.text()
                    io_profile("write", self.profile_id, "profile", "watched_config_folders", selected_folder, "remove")
                    config_editor_add_folders_dialog.listWidget.takeItem(config_editor_add_folders_dialog.listWidget.row(selected_item))
                    if config_editor_add_folders_dialog.listWidget.count() == 0:
                        config_editor_add_folders_dialog.listWidget.setEnabled(False)

        config_editor_add_folders_dialog.addButton.clicked.connect(add_folder)
        config_editor_add_folders_dialog.removeButton.clicked.connect(remove_folder)
        config_editor_add_folders_dialog.closeButton.clicked.connect(config_editor_add_folders_dialog.close)

        config_editor_add_folders_dialog.exec_()


    def update_filter(self, text):
        search = QRegExp(text, Qt.CaseInsensitive, QRegExp.FixedString)
        self.proxy_model.setFilterRegExp(search)
        self.editor_table_view.viewport().update()

        self.editor_table_view.verticalHeader().setVisible(False)

        self.file_combo_box.currentIndexChanged.connect(self.populate_section_combo_box)
        self.section_combo_box.currentIndexChanged.connect(self.populate_table_view)

        self.populate_table_view()


    def handle_item_changed(self, topLeft, bottomRight):
        bold_font = QtGui.QFont()
        bold_font.setBold(True)

        for row in range(topLeft.row(), bottomRight.row() + 1):
            for column in range(topLeft.column(), bottomRight.column() + 1):
                item = self.table_model.item(row, column)
                item.setFont(bold_font)

        row = topLeft.row()
        key = self.table_model.item(row, 0).text()
        value_text = self.table_model.item(row, 1).text()
        
        file_path = self.file_combo_box.currentText()
        section = self.section_combo_box.currentText() + '/'
        
        complete_key = section + key
        file_format = self.file_formats.get(file_path)
        if file_format == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                flattened_data = self.flatten_json(data)
                if complete_key in flattened_data:
                    original_value = flattened_data[complete_key]
                    if isinstance(original_value, (int, float)):
                        try:
                            value = float(value_text)
                            if value.is_integer():
                                value = int(value)
                        except ValueError:
                            msgBox = QMessageBox()
                            msgBox.setWindowTitle("Input Error")
                            msgBox.setText(f"Invalid input for field {key}. This field requires a numerical value.")
                            msgBox.exec_()

                            normal_font = QtGui.QFont()
                            normal_font.setBold(False)
                            self.table_model.item(row, 1).setText(str(original_value))
                            self.table_model.item(row, 1).setFont(normal_font)


    def populate_file_combo_box(self):
        profile_data = io_profile("read", self.profile_id, "profile")
        watched_config_folders = profile_data.get("watched_config_folders", [])

        file_paths = []
        for folder in watched_config_folders:
            for root, dirs, files in os.walk(folder):
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


    def populate_section_combo_box(self):
        file_path = self.file_combo_box.currentText()

        self.section_combo_box.clear()
        self.section_combo_box.addItem("Section")

        if file_path == "Files":
            return

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
        
        self.initial_values = {}

        if file_format == '.ini':
            config = configparser.ConfigParser()
            config.read(file_path)

            if section in config:
                for key, value in config.items(section):
                    self.add_row_to_table(key, value)
                    self.initial_values[key] = value

        elif file_format == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                flattened_data = self.flatten_json(data)

                section += '/'

                for key in flattened_data:
                    if key.startswith(section):
                        modified_key = key.replace(section, '')
                        value = flattened_data[key]
                        if '/' not in modified_key:
                            self.add_row_to_table(modified_key, str(value))
                            self.initial_values[modified_key] = str(value)

                stripped_section = section.strip('/')
                if stripped_section in data and not isinstance(data[stripped_section], (dict, list)):
                    self.add_row_to_table("Value", str(data[stripped_section]))
                    self.initial_values["Value"] = str(data[stripped_section])

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
        if self.file_combo_box.currentText() == "Files" or self.section_combo_box.currentText() == "Section":
            return

        file_path = self.file_combo_box.currentText()

        backup_folder_path = os.path.join(user_config_file, "config_backup", str(self.profile_id))
        path_parts = os.path.normpath(file_path).split(os.sep)
        necessary_part_path = os.path.join(*(path_parts[0].replace(':', ''), *path_parts[1:]))
        backup_file_path = os.path.join(backup_folder_path, necessary_part_path)

        os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)

        if not os.path.exists(backup_file_path):
            shutil.copy2(file_path, backup_file_path)


        def recursive_update(json_data, keys, value):
            key = keys.pop(0)
            if keys:
                if key not in json_data:
                    json_data[key] = {}
                recursive_update(json_data[key], keys, value)
            else:
                json_data[key] = value


        file_format = self.file_formats.get(file_path)
        if file_format == '.ini':
            config = configparser.ConfigParser()
            config.read(file_path)
            
            section = self.section_combo_box.currentText()

            for row in range(self.table_model.rowCount()):
                key = self.table_model.item(row, 0).text()
                value = self.table_model.item(row, 1).text()

                if not config.has_section(section):
                    config.add_section(section)
                
                config.set(section, key, value)

            with open(file_path, 'w') as file:
                config.write(file)

        elif file_format == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
                flattened_data = self.flatten_json(data)
                section = self.section_combo_box.currentText() + '/'
                for row in range(self.table_model.rowCount()):
                    key = self.table_model.item(row, 0).text()
                    value_text = self.table_model.item(row, 1).text()
                    complete_key = section + key
                    if complete_key in flattened_data:
                        original_value = flattened_data[complete_key]
                        keys = complete_key.split('/')
                        sub_data = data
                        for sub_key in keys[:-1]:
                            sub_data = sub_data[sub_key]

                        if isinstance(original_value, (int, float)):
                            try:
                                value = float(value_text)
                                if value.is_integer():
                                    value = int(value)
                            except ValueError:
                                if not value_text.replace('.', '', 1).isdigit():
                                    value = value_text
                                else:
                                    msgBox = QMessageBox()
                                    msgBox.setWindowTitle("Input Error")
                                    msgBox.setText(f"Invalid input for field {key}. This field requires a numerical value.")
                                    msgBox.exec_()
                                    return
                        else:
                            value = value_text

                        sub_data[keys[-1]] = value

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)

        msgBox = QMessageBox()
        msgBox.setWindowTitle("Config File Saved")
        msgBox.setText(f"The configuration file has been saved successfully.\n\nNote: An original version of this file is permanently stored here, even if you make further changes:\n\n{backup_file_path}")
        msgBox.exec_()


    def reset_changes(self):
        self.table_model.dataChanged.disconnect(self.handle_item_changed)

        for row in range(self.table_model.rowCount()):
            key_item = self.table_model.item(row, 0)
            value_item = self.table_model.item(row, 1)

            key = key_item.text()
            initial_value = self.initial_values.get(key)
            current_value = value_item.text()
                            
            normal_font = QtGui.QFont()
            if str(initial_value) != current_value:
                normal_font.setBold(False)
                value_item.setFont(normal_font)

            if initial_value is not None:
                value_item.setText(str(initial_value))

        self.table_model.dataChanged.connect(self.handle_item_changed)


    def restore_backup(self):
        if self.file_combo_box.currentText() == "Files":
            return

        original_file_path = self.file_combo_box.currentText()

        backup_folder_path = os.path.join(user_config_file, "config_backup", str(self.profile_id))
        hostname = socket.gethostname()
        path_parts = os.path.normpath(original_file_path).split(os.sep)
        necessary_part_path = os.path.join(*(hostname, path_parts[0].replace(':', ''), *path_parts[1:]))
        backup_file_path = os.path.join(backup_folder_path, necessary_part_path)

        if os.path.exists(backup_file_path):
            shutil.copy2(backup_file_path, original_file_path)

            msgBox = QMessageBox()
            msgBox.setWindowTitle("Config File Restored")
            msgBox.setText(f"The configuration file has been restored to the backup version.\n\nThe restored version is stored:\n{original_file_path}")
            msgBox.exec_()

            self.populate_table_view()
        else:
            msgBox = QMessageBox()
            msgBox.setWindowTitle("No Backup File")
            msgBox.setText(f"No backup file found to restore. It may not have been backed up or the backup was deleted.")
            msgBox.exec_()

        msgBox = QMessageBox()
        msgBox.setWindowTitle("Config File Saved")
        msgBox.setText(f"The configuration file has been saved successfully.\n\nThe original version prior to any changes made here is stored:\n{backup_file_path}")
        msgBox.exec_()

    def save_changes_and_close(self):
        self.save_changes()
        self.accept()