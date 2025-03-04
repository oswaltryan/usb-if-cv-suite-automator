'''
Python wrapper for usbview-cli console application.
'''

import xml.etree.ElementTree as XMLTree
from dataclasses import dataclass
from typing import Sequence
from pathlib import Path
import subprocess
from pprint import pprint
import win32com.client

## Get drive size
def bytes_to_gb(bytes_value):
    return bytes_value / (1024 ** 3)

def find_closest(target, options):
    # Return the element in 'options' with the smallest absolute difference from target
    return min(options, key=lambda x: abs(x - target))

# Example list of 8 values in GB
closest_values = [2, 4, 8, 16, 32, 64, 128, 256, 512]

locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
service = locator.ConnectServer(".", "root\\cimv2")

query = "SELECT * FROM Win32_DiskDrive WHERE InterfaceType='USB'"
usb_drives = service.ExecQuery(query)

for drive in usb_drives:
    size_bytes = int(drive.Size)
    size_gb = bytes_to_gb(size_bytes)
    closest_match = find_closest(size_gb, closest_values)
    # print(f"Device: {drive.Caption}")
    # print(f"Size: {size_gb:.2f} GB")
    # print(f"Closest match from list: {closest_match} GB")


# Define the path to the usbview-cli executable
EXE = r"C:\Users\itadmin\Desktop\cv_suite_testing\usbview-cli-0.1.0\usbview-cli.exe"

class UsbTreeError(Exception):
    ''' Custom exception for USB tree errors '''
    def __init__(self, msg):
        self.msg = msg

class ExtractionError(Exception):
    ''' Exception raised when extraction of device info fails '''
    pass

@dataclass
class WinUsbDeviceInfo:
    ''' Dataclass representing a USB device information structure '''
    idProduct: str
    idVendor: str
    bcdDevice: str
    bcdUSB: str
    iManufacturer: str
    iProduct: str
    iSerial: str
    device_id: str
    vendor: str
    usb_protocol: str
    usbController: str = ""  # Stores controller name
    SCSIDevice: str = ""     # Stores UASP status (True/False as string)
    driveSize: str = ""      # Stores the device volume size rounded to the nearest multiple of significance

def list_devices_info(vids: Sequence[str] = []) -> list[WinUsbDeviceInfo]:
    '''
    Retrieves a list of USB devices, optionally filtered by vendor IDs.
    '''
    devs = []
    for el in get_usb_tree().iterfind('.//UsbDevice'):
        try:
            dev = _extract_device_info(el)
        except ExtractionError:
            continue
        else:
            devs.append(dev)
    
    if vids:
        vids = [x.lower() for x in vids]
        devs = list(filter(lambda dev: dev.idVendor in vids, devs))
    
    return devs

def get_usb_tree() -> XMLTree.Element:
    '''
    Retrieves the USB tree as an XML element.
    '''
    cmd = [str(EXE)]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
    except Exception as e:
        raise UsbTreeError(f"Failed to execute command: {e}")
    
    if result.returncode != 0:
        raise UsbTreeError(f"usbtree-cli returned non-zero exit code {result.returncode}")
    
    try:
        return XMLTree.fromstring(result.stdout)
    except Exception as e:
        raise UsbTreeError(f"Error parsing usbtree-cli output: {e}")

def _extract_device_info(el: XMLTree.Element) -> WinUsbDeviceInfo:
    '''
    Extracts device information from an XML element.
    '''
    device_id, usb_protocol = el.get('DeviceId'), el.get('UsbProtocol')
    dscptr = el.find('./ConnectionInfo/ConnectionInfoStruct/DeviceDescriptor')
    
    if not device_id or not usb_protocol or dscptr is None:
        raise ExtractionError()
    
    bcdDevice, bcdUSB = dscptr.get('BcdDevice'), dscptr.get('BcdUSB')
    idVendor, idProduct = dscptr.get('IdVendor'), dscptr.get('IdProduct')
    
    if not (bcdDevice and bcdUSB and idVendor and idProduct):
        raise ExtractionError()
    
    return WinUsbDeviceInfo(
        device_id=device_id,
        usb_protocol=usb_protocol,
        idProduct=_to_hex_s(idProduct).lower(),
        idVendor=_to_hex_s(idVendor).lower(),
        bcdDevice=_to_hex_s(bcdDevice),
        bcdUSB=_parse_bcdUSB(bcdUSB),
        iManufacturer=_find_txt_or_blank(el, './ConnectionInfo/ManufacturerString'),
        iProduct=_find_txt_or_blank(el, './ConnectionInfo/ProductString'),
        iSerial=_find_txt_or_blank(el, './ConnectionInfo/SerialString'),
        vendor=_find_txt_or_blank(el, './ConnectionInfo/VendorString'),
    )

def _find_txt_or_blank(el: XMLTree.Element, xpath: str) -> str:
    ''' Retrieves text from an XML element or returns an empty string '''
    res = el.find(xpath)
    return _make_blank_if_missing(res.text if res is not None else '')

def _make_blank_if_missing(txt: str) -> str:
    ''' Converts error indicators into an empty string '''
    return '' if txt.startswith("ERROR") or txt == '?' else txt

def _parse_bcdUSB(bcdUSB: str) -> str:
    ''' Converts a USB version string from hexadecimal '''
    hex_s = _to_hex_s(bcdUSB)
    return f"{int(hex_s[0:2])}.{hex_s[2:]}"

def _to_hex_s(int_str: str) -> str:
    ''' Converts an integer string to a zero-padded hexadecimal string '''
    try:
        return f"{int(int_str):0>4x}"
    except ValueError:
        raise ExtractionError()

def find_apricorn_device():
    '''
    Searches for an Apricorn device among USB devices.
    '''
    output = list_devices_info()
    
    for item in output:
        if item.idProduct == '0351':
            continue
        
        item.SCSIDevice = "True" if "MSFT30" in item.device_id else "False"
        
        ps_script = rf'''
            $vendor = "{item.idVendor}"
            Get-CimInstance Win32_USBControllerDevice | ForEach-Object {{
                $device = Get-CimInstance -CimInstance $_.Dependent
                if (($device.DeviceID -like "*VID_$vendor*") -and ($device.DeviceID -notlike "*0351*")) {{
                    $controller = Get-CimInstance -CimInstance $_.Antecedent
                    Write-Output $controller.Name
                }}
            }}
            '''
        
        result = subprocess.run(["powershell.exe", "-Command", ps_script],
                                capture_output=True, text=True)
        item.usbController = result.stdout.strip()
        
        if item.idVendor == '0984':
            item.driveSize = closest_match
            if 'Intel' in item.usbController:
                item.usbController = 'Intel'
            elif 'ASMedia' in item.usbController:
                item.usbController = 'ASMedia'
            return item

## Example Usage
# info = find_apricorn_device()
# pprint(info)
