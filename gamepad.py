import inputs
import threading

controls = {}
class Gamepad():
    def __init__(self):
        self.state = {"ABS_X": 0, "ABS_Y": 0, "ABS_RX": 0, "ABS_RY": 0, "ABS_Z": 0, "ABS_RZ": 0}
        self.thread = threading.Thread(target=self.handle_events)
        self.thread.daemon = True
        self.thread.start()

    def handle_events(self):
        while True:
            events = inputs.get_gamepad()
            for ev in events:
                self.state[ev.code] = ev.state

    def get_state(self):
        return self.state
