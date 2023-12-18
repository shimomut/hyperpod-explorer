
class SuspendTui:
    
    def __init__(self, app):
        self.app = app
    
    def __enter__(self):
        self.app._driver.stop_application_mode()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.app.refresh()
        self.app._driver.start_application_mode()
