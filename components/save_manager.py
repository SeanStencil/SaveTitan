import os
import shutil

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMessageBox, QInputDialog, QListWidgetItem
from PyQt5.QtCore import Qt

from modules.io import io_profile
from modules.io import io_global
from modules.io import io_savetitan
from modules.io import copy_save_to_cloud
from modules.io import copy_save_to_local

from modules.misc import center_dialog_over_dialog

import modules.paths as paths
user_config_file = paths.user_config_file
global_config_file = paths.global_config_file


# Function to open save management dialog
def save_mgmt_dialog(profile_id):
    save_mgmt_dialog = uic.loadUi("ui/save_mgmt.ui")
    save_mgmt_dialog.setWindowFlags(save_mgmt_dialog.windowFlags() & ~Qt.WindowMaximizeButtonHint)
    save_mgmt_dialog.setFixedSize(save_mgmt_dialog.size())

    cloud_storage_path = io_global("read", "config", "cloud_storage_path")
    profile_folder = os.path.join(cloud_storage_path, profile_id)

    save_mgmt_dialog.profilenameField.setText(io_savetitan("read", profile_id, "profile", "name"))
    save_mgmt_dialog.saveField.setText(io_profile("read", profile_id, "profile", "local_save_folder"))

    save_slot = io_profile("read", profile_id, "profile", "save_slot")
    save_slot_key = f"save{save_slot}"

    save_slot_name = io_savetitan("read", profile_id, "saves", save_slot_key)
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
        io_savetitan("write", profile_id, "profile", "saves", str(number_of_saves))

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
            copy_save_to_cloud(profile_id, True)

        new_save_slot = selected_save_key.replace('save', '')
        
        io_profile("write", profile_id, "profile", "save_slot", new_save_slot)

        save_mgmt_dialog.saveslotField.setText(selected_item.text())

        copy_save_to_local(profile_id, True)

        QMessageBox.information(None, "Load Finished", "The selected save has been loaded successfully.")


    def handle_delete_save_button():
        selected_items = save_mgmt_dialog.save_listWidget.selectedItems()
        if not selected_items:
            return

        selected_item = selected_items[0]
        selected_save_key = selected_item.data(Qt.UserRole)

        current_save_slot = io_profile("read", profile_id, "profile", "save_slot")
        current_save_key = f"save{current_save_slot}"
        if selected_save_key == current_save_key:
            QMessageBox.warning(save_mgmt_dialog, "Delete Error", "You can't delete a save that is currently loaded.")
            return

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