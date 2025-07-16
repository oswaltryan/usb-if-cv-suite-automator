import sys
import asyncio
import time
import logging
from usb_tool import find_apricorn_device
class UsbAutoLockTest:
    def __init__(self, poll_interval=10):
        self.poll_interval = poll_interval
        self.target_device = None

    async def select_device(self):
        logging.info("Searching for Apricorn device...")
        devices = find_apricorn_device()  # Now returns a list
        
        if not devices:
            logging.error("No Apricorn devices found.")
            sys.exit(1)
            
        # Select first device by default (maintain original behavior)
        self.target_device = devices[0]
        
        if len(devices) > 1:
            logging.warning(f"Found {len(devices)} devices. Using first one:")
            for idx, dev in enumerate(devices):
                logging.warning(f"{idx+1}. {dev.iProduct} (SN: {dev.iSerial})")
        
        logging.info(f"Target device selected: {self.target_device.iProduct} "
                     f"({self.target_device.idVendor}:{self.target_device.idProduct})")
        logging.info(f"Device Serial: {self.target_device.iSerial}, Protocol: {self.target_device.bcdUSB}")
        logging.info("Press ENTER to start the test.")
        await asyncio.to_thread(input)

    def check_device_presence(self):
        # Lightweight check using WMI only.
        usb_devices = find_apricorn_device()
        for dev in usb_devices:
            if (dev['vid'] == self.target_device.idVendor and 
                dev['pid'] == self.target_device.idProduct and 
                dev['serial'] == self.target_device.iSerial):
                return True
        return False

    async def autolock_test(self, minutes):
        start = time.time()
        end = start + minutes * 60

        while time.time() < end:
            if not self.check_device_presence():
                elapsed = int(time.time() - start)
                logging.error(f"Device removed too early at {elapsed}s; expected ~{minutes}m.")
                return False
            elapsed = int(time.time() - start)
            logging.info(f"Time Elapsed: {elapsed}s | Device is present.")
            await asyncio.sleep(self.poll_interval)

        # Final check
        if not self.check_device_presence():
            logging.info(f"Device removed as expected after {minutes}m.")
            return True

        logging.error(f"Device still present after {minutes}m.")
        return False

    async def run_tests(self):
        await self.select_device()
        intervals = [5, 10, 20]
        results = []

        for i, m in enumerate(intervals):
            logging.info(f"Starting auto-lock test for {m}m...")
            passed = await self.autolock_test(m)
            results.append(passed)
            logging.info(f"Test {'PASS' if passed else 'FAIL'} for {m}m.")

            if i < len(intervals) - 1:
                logging.info("Press ENTER to proceed to the next test.")
                await asyncio.to_thread(input)

        all_pass = all(results)
        logging.info(f"Overall test result: {'PASS' if all_pass else 'FAIL'}")
        return all_pass

if __name__ == "__main__":
    test = UsbAutoLockTest()
    overall = asyncio.run(test.run_tests())
    sys.exit(0 if overall else 1)
