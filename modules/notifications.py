from modules.io import io_global


def send_notification(title, message):
    import sys
    if sys.platform == "win32":  # Windows
        from plyer import notification
        notification.notify(title=title, message=message)
    elif sys.platform == "darwin":  # MacOS
        from pync import Notifier
        Notifier.notify(message, title=title)
    elif sys.platform.startswith("linux"):  # Linux
        import notify2
        notify2.init('SaveTitan')
        notification = notify2.Notification(title, message)
        notification.show()

def debug_msg(message):
    if io_global("read", "config", "debug") == "enable":
        print('DEBUG MSG: ' + message)