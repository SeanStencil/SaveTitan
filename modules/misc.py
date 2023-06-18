from PyQt5.QtCore import QTimer


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