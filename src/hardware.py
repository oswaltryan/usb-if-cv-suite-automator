from Phidget22.Phidget import *
from Phidget22.Devices.DigitalOutput import DigitalOutput

class IOController:
    def __init__(self):
        self.outputs = {
            'power': self._initialize_output(13),
            'usb3': self._initialize_output(14)
        }

    def _initialize_output(self, channel):
        output = DigitalOutput()
        output.setChannel(channel)
        output.openWaitForAttachment(5000)
        return output

    def turn_on(self, name):
        if name in self.outputs:
            # print(f"Turning on {name}...")
            self.outputs[name].setDutyCycle(1)

    def turn_off(self, name):
        if name in self.outputs:
            # print(f"Turning off {name}...")
            self.outputs[name].setDutyCycle(0)

    def close(self):
        for output in self.outputs.values():
            output.close()

# Example usage (to be used in other scripts):
# from phidget_controller import IOController
# controller = IOController()              # Initialize controller
# controller.turn_on('power')               # Turn on power (channel 13)
# controller.turn_off('power')              # Turn off power (channel 13)
# controller.turn_on('usb3')                # Turn on USB3 (channel 14)
# controller.turn_off('usb3')               # Turn off USB3 (channel 14)
# controller.close()                        # Close all controller connections
