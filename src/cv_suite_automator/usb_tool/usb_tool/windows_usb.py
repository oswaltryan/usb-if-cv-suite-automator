from collections import defaultdict
import ctypes as ct
from dataclasses import dataclass
import json
import libusb as usb
from pprint import pprint
import re
import subprocess
import win32com.client

# Configure libusb to use the included libusb-1.0.dll
usb.config(LIBUSB=None)

# ==================================
# Helper Functions
# ==================================

def bytes_to_gb(bytes_value):
    """Convert bytes to gigabytes."""
    return bytes_value / (1024 ** 3)

def find_closest(target, options):
    """Find the closest value in 'options' to 'target'."""
    closest = min(options, key=lambda x: abs(x - target))
    return int(closest)

def parse_usb_version(bcd):
    """Convert a BCD USB version to a human-readable string (e.g., '2.0', '3.1')."""
    major = (bcd & 0xFF00) >> 8
    minor = (bcd & 0x00F0) >> 4
    subminor = bcd & 0x000F
    if subminor:
        return f"{major}.{minor}{subminor}"
    return f"{major}.{minor}"

def read_string_descriptor_ascii(handle, index):
    """Read a string descriptor from a USB device and return it as ASCII."""
    if index == 0:
        return ""
    buf = (ct.c_ubyte * 256)()
    rc = usb.get_string_descriptor_ascii(handle, index, buf, ct.sizeof(buf))
    if rc < 0:
        return ""
    return bytes(buf[:rc]).decode("utf-8", errors="replace")

def get_all_usb_controller_names():
    """
    Retrieve information for Apricorn devices (VID '0984') on the system.
    Returns a list of dictionaries, each containing keys 'DeviceID' and 'ControllerName'.
    """
    ps_script = r'''
    Get-CimInstance Win32_USBControllerDevice | ForEach-Object {
        $controller = Get-CimInstance -CimInstance $_.Antecedent
        $device = Get-CimInstance -CimInstance $_.Dependent
        if ($device.DeviceID -like "*VID_0984*") {
            [PSCustomObject]@{
                DeviceID = $device.DeviceID
                ControllerName = $controller.Name
            }
        }
    } | ConvertTo-Json
    '''
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"PowerShell error: {result.stderr}")
        return []

    try:
        data = json.loads(result.stdout)

        # In case a single object was returned, wrap it in a list
        if isinstance(data, dict):
            data = [data]

        # Convert to a list of dictionaries, normalizing DeviceID to uppercase
        usb_controllers = [
            {
                'DeviceID': item['DeviceID'].upper(),
                'ControllerName': item['ControllerName'][:5] if item['ControllerName'].startswith('Intel') else 'ASMedia'
            }
            for item in data if "0221" not in item['DeviceID'] if "0301" not in item['DeviceID'] 
        ]

        # print("USB Controllers:")
        # pprint(usb_controllers)
        # print()
        return usb_controllers

    except json.JSONDecodeError:
        # print("Failed to parse PowerShell output")
        return []


# ==================================
# Dataclasses and Custom Errors
# ==================================

class UsbTreeError(Exception):
    """Custom exception for USB tree errors."""
    pass

@dataclass
class WinUsbDeviceInfo:
    """
    Dataclass representing a USB device information structure.
    Includes busNumber and deviceAddress to differentiate devices.
    """
    bcdUSB: float
    idVendor: str
    idProduct: str
    bcdDevice: str
    iManufacturer: str
    iProduct: str
    iSerial: str
    SCSIDevice: bool = False
    driveSizeGB: int = 0
    usbController: str = ""
    busNumber: int = 0
    deviceAddress: int = 0
    physicalDriveNum: int = 0
    driveLetter: str = "N/A"
    mediaType: str = "Unknown"
    readOnly: bool = False

# ==================================
# Gathering Apricorn Device Info
# ==================================

locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
service = locator.ConnectServer(".", "root\\cimv2")

# Location: usb_tool/windows_usb.py
# Add this function after the WinUsbDeviceInfo dataclass.

def get_drive_letter_via_ps(drive_index: int) -> str:
    """
    Executes a targeted PowerShell script (based on user-provided logic) to
    find the drive letter(s) for a specific physical disk index.

    This is a highly reliable method that avoids previous WMI/COM issues.

    Args:
        drive_index (int): The physical drive number (e.g., 1).

    Returns:
        str: A comma-separated string of drive letters (e.g., "E:, F:") or "N/A".
    """
    import subprocess

    # A drive index less than 0 is invalid.
    if drive_index < 0:
        return "N/A"

    # This is your PowerShell script, slightly modified to collect and output
    # all drive letters on a single line for easy parsing by Python.
    ps_script = f"""
    $driveLetters = Get-WmiObject -Query "SELECT * FROM Win32_DiskDrive WHERE Index = {drive_index}" |
    ForEach-Object {{
        $drive = $_
        $partitions = Get-WmiObject -Query "ASSOCIATORS OF {{Win32_DiskDrive.DeviceID='$($drive.DeviceID)'}} WHERE AssocClass = Win32_DiskDriveToDiskPartition"
        foreach ($partition in $partitions) {{
            $logicalDisks = Get-WmiObject -Query "ASSOCIATORS OF {{Win32_DiskPartition.DeviceID='$($partition.DeviceID)'}} WHERE AssocClass = Win32_LogicalDiskToPartition"
            foreach ($logical in $logicalDisks) {{
                $logical.DeviceID
            }}
        }}
    }}
    # Join multiple letters (e.g., for a partitioned drive) into one string
    $driveLetters -join ', '
    """

    try:
        # Execute the script, hiding the console window.
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        
        # Get the output and remove any leading/trailing whitespace.
        output = result.stdout.strip()
        
        return output if output else "N/A"

    except (subprocess.CalledProcessError, FileNotFoundError):
        # If the script fails for any reason, return "N/A".
        return "N/A"

def get_wmi_usb_devices():
    """
    Fetch all USB devices from WMI (Win32_PnPEntity) whose DeviceID starts with 'USB\\VID_'.
    Returns a list of dicts with relevant info (VID, PID, manufacturer, description, serial).
    """
    query = "SELECT * FROM Win32_PnPEntity WHERE DeviceID LIKE 'USB%'"
    usb_devices = service.ExecQuery(query)

    devices_info = []
    for device in usb_devices:
        device_id = device.DeviceID
        if not device_id.upper().startswith("USB\\VID_") or "0984" not in device_id:
            continue

        parts = device_id.split("\\", 2)
        if len(parts) < 2:
            continue

        vid_pid = parts[1].split("&")
        vid = vid_pid[0].replace('VID_', '').lower()
        pid = vid_pid[1].replace('PID_', '').lower()
        serial = parts[2] if len(parts) > 2 else ""

        if pid == "0221" or pid == "0301":
            continue

        devices_info.append({
            "vid": vid,
            "pid": pid,
            "manufacturer": "Apricorn",
            "description": device.Description or "",
            "serial": serial
        })

    # print("wmi_usb_devices:")
    # pprint(devices_info)
    # print()
    return devices_info

def get_wmi_usb_drives():
    """
    Fetch all USB drives from WMI (Win32_DiskDrive WHERE InterfaceType='USB').
    Returns a list of dicts with caption, size in GB, closest_match, iProduct, pnpdeviceid, etc.
    """
    wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")
    query = "SELECT * FROM Win32_DiskDrive WHERE InterfaceType='USB'"  # Filter for USB drives
    usb_drives = service.ExecQuery(query) #changed from wmi.ExecQuery
    drives_info = []
    
    for drive in usb_drives:
        if "Apricorn" in getattr(drive, "Caption"):
            # for prop in drive.Properties_:
            #     print(prop.Name, "=", prop.Value)
            # print()
            if getattr(drive, "Size", None) is None:
                continue
            try:
                size_bytes = int(drive.Size)
            except (TypeError, ValueError):
                continue
            
            pnp = drive.PNPDeviceID
            if not pnp:
                continue           

            media_type_wmi = getattr(drive, "MediaType", "Unknown type")
            media_type = "Unknown"
            if "External hard disk media" in media_type_wmi:
                media_type = "Basic Disk"
            elif "Removable" in media_type_wmi:
                media_type = "Removable Media"

            try:
                if 'USBSTOR' in pnp:
                    i_product = pnp[pnp.index("PROD_") + 5 : pnp.index("&REV")].replace('_', ' ').title()
                elif 'SCSI' in pnp:
                    i_product = pnp.split("PROD_", 1)[1].split("\\", 1)[0].replace('_', ' ')
                    if "NVX" in i_product:
                        i_product = "Padlock NVX" if i_product == "PADLOCK NVX" else ""
                    elif "PORTABLE" in i_product:
                        i_product = "Aegis Portable" if i_product == " AEGIS PORTABLE" else ""
            except ValueError:
                i_product = ""

            size_gb = bytes_to_gb(size_bytes)
            
            drives_info.append({
                "caption": drive.Caption,
                "size_gb": size_gb,
                "iProduct": i_product,
                "pnpdeviceid": pnp,
                "mediaType": media_type
            })

    # print("wmi_usb_drives:")
    # pprint(drives_info)
    # print()
    return drives_info

def get_apricorn_libusb_data():
    """
    Use libusb to iterate over USB devices and collect info for Apricorn devices (VID '0984').
    Assign controller names in batch after enumeration.
    """
    devices = []
    ctx = ct.POINTER(usb.context)()
    rc = usb.init(ct.byref(ctx))
    if rc != 0:
        raise UsbTreeError("Failed to initialize libusb")
    try:
        dev_list = ct.POINTER(ct.POINTER(usb.device))()
        cnt = usb.get_device_list(ctx, ct.byref(dev_list))
        if cnt < 0:
            raise UsbTreeError("Failed to get device list")

        for i in range(cnt):
            dev = dev_list[i]
            desc = usb.device_descriptor()
            rc = usb.get_device_descriptor(dev, ct.byref(desc))
            if rc != 0:
                continue

            idVendor = f"{desc.idVendor:04x}"
            if idVendor != "0984":  # Filter for Apricorn devices
                continue

            # Core descriptors
            idProduct = f"{desc.idProduct:04x}"
            bcdDevice = f"{desc.bcdDevice:04x}"
            bcdUSB = float(parse_usb_version(desc.bcdUSB))
            bus_number = usb.get_bus_number(dev)
            dev_address = usb.get_device_address(dev)

            if idProduct == "0221" or idProduct == "0301":
                continue

            devices.append({
                "iProduct": idProduct,
                "bcdDevice": bcdDevice,
                "bcdUSB": bcdUSB,
                "bus_number": bus_number,
                "dev_address": dev_address
            })

        usb.free_device_list(dev_list, 1)

    finally:
        usb.exit(ctx)

    # print("libusb devices:")
    # pprint(devices)
    # print()
    return devices if devices else None

import win32com.client
import re

def get_physical_drive_number():
    """
    Retrieves the physical drive number associated with a given PNPDeviceID.
    
    Returns:
        str: The physical drive number (e.g., "0", "1"), or None if not found.
    """
    physical_drives = {}
    try:
        wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")

        # 1. Get all Win32_DiskDrive instances
        query = "SELECT DeviceID, PNPDeviceID FROM Win32_DiskDrive"

        results = wmi.ExecQuery(query)

        for result in results:
            drive_pnp_id = result.PNPDeviceID.rsplit('\\', 1)[1][:-2]
            drive_device_id = int(result.DeviceID[-1:])
            # print(f"Debugging: Drive PNPDeviceID: {result.PNPDeviceID}")
            # print(f"Debugging: Drive DeviceID: {result.DeviceID}")

            if "SATAWIRE" in result.PNPDeviceID or "FLASH_DISK" in result.PNPDeviceID:
                continue

            if "APRI" in result.PNPDeviceID:
                physical_drives.update({drive_pnp_id: drive_device_id})
        
        if physical_drives == {}:
            return None
        else:
            # print("Physical Drives:")
            # pprint(physical_drives)
            # print()
            return physical_drives

    except Exception as e:
        print(f"Error getting physical drive number(s): {e}")
        return None
    
def get_usb_readonly_status_map():
    """
    Uses a robust PowerShell command to build a map of physical USB disk
    numbers to their read-only status.

    Returns:
        dict: A dictionary where keys are integer disk numbers and the value
              is a boolean (True if read-only, False otherwise).
              Example: {1: True, 2: False}
    """

    # This simple script gets all USB disks and selects just their number
    # and their read-only state, then outputs as clean JSON.
    ps_script = r"""
    Get-Disk | Where-Object { $_.Bustype -eq 'USB' } |
    Select-Object -Property Number, IsReadOnly |
    ConvertTo-Json -Compress
    """

    readonly_map = {}
    try:
        # Execute the command, hiding the PowerShell window.
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, check=True, creationflags=0x08000000 # CREATE_NO_WINDOW
        )

        if not result.stdout.strip():
            return {}

        data = json.loads(result.stdout)
        if isinstance(data, dict): data = [data] # Handle single-item case

        for item in data:
            disk_number = int(item['Number'])
            is_readonly = bool(item['IsReadOnly'])
            readonly_map[disk_number] = is_readonly

    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, KeyError):
        # On any failure, return an empty map, assuming no disks are read-only.
        return {}

    return readonly_map

# ==================================
# Process Apricorn Device Info
# ==================================

def sort_wmi_drives(wmi_usb_devices, wmi_usb_drives):
    """
    Sorts the wmi_drives list to match the order of wmi_devices.

    Relies on matching serial numbers, handling variations like prefixes
    (e.g., 'MSFT30...') and serial numbers embedded in PNPDeviceIDs.
    Handles SCSI devices as a fallback if serial matching fails.
    """
    sorted_drives = []
    # Make a mutable copy to safely remove items from during processing
    drives_to_process = list(wmi_usb_drives)

    for device in wmi_usb_devices:
        device_serial = device.get('serial', '') # Use .get for safety
        device_desc = device.get('description', '')
        found_index = -1 # Index of the drive found in drives_to_process

        # Special handling for known SCSI devices based on description if serial is unreliable/absent
        is_scsi_device = 'SCSI' in device_desc or (device_serial and device_serial.startswith('MSFT30'))

        best_match_score = -1 # Use a score for better matching prio

        for i, drive in enumerate(drives_to_process):
            pnp_id = drive['pnpdeviceid']
            current_score = -1

            # Extract the instance ID part (usually after the last '\')
            instance_id = pnp_id.rsplit('\\', 1)[-1]

            # Extract the potential serial number part from the instance ID (before potential '&')
            ampersand_pos = instance_id.find('&')
            pnp_serial_part = instance_id[:ampersand_pos] if ampersand_pos != -1 else instance_id

            # --- Scoring Logic ---
            # Score 3: Exact match between device serial and PNP serial part
            if device_serial and device_serial == pnp_serial_part:
                current_score = 3
            # Score 2: Device serial contains PNP serial part OR vice-versa (Handles prefixes/suffixes)
            elif device_serial and pnp_serial_part and (pnp_serial_part in device_serial or device_serial in pnp_serial_part):
                 current_score = 2
            # Score 1: If it's a known SCSI device type and the drive is SCSI (fallback)
            elif is_scsi_device and "SCSI" in pnp_id and "PADLOCK_NVX" in pnp_id: # Be specific if possible
                 # Ensure this SCSI drive hasn't been matched by a higher score rule already
                 # This simplistic check assumes only one such SCSI drive.
                 current_score = 1

            # Update best match if current score is higher
            if current_score > best_match_score:
                best_match_score = current_score
                found_index = i

        # If a reasonably confident match was found (Score > 0)
        if found_index != -1 and best_match_score > 0:
            # Remove the drive from the processing list and append it to the sorted list.
            found_drive = drives_to_process.pop(found_index)
            sorted_drives.append(found_drive)
        else:
            # If no match found for this device, add a placeholder or handle error
            # For simplicity here, we'll append None, but you might need robust error handling
             print(f"Warning: No matching drive found for WMI device: {device_serial} / {device_desc}")
             sorted_drives.append(None) # Add placeholder

    # Append any remaining drives that were not matched to any device (might be unexpected drives)
    if drives_to_process:
        print(f"Warning: Appending {len(drives_to_process)} unmatched drives to the end:")
        pprint(drives_to_process)
        sorted_drives.extend(drives_to_process) # Or handle as errors

    # Filter out potential None placeholders if added
    sorted_drives_filtered = [drive for drive in sorted_drives if drive is not None]

    wmi_usb_drives = sorted_drives_filtered

    # # --- Output and Verification ---
    # print("SORTED ----------")
    # print("wmi_usb_devices: ")
    # pprint(wmi_usb_devices)
    # print()
    # print("wmi_usb_drives: ")
    # pprint(wmi_usb_drives)
    return wmi_usb_drives

def sort_usb_controllers(wmi_usb_devices, usb_controllers):
    # --- Sorting Logic ---
    sorted_controllers = []
    # Make a mutable copy to safely remove items from during processing
    controllers_to_process = list(usb_controllers)

    for device in wmi_usb_devices:
        target_serial = device['serial']
        found_index = -1 # Index of the controller found in controllers_to_process

        # Iterate through the remaining controllers to find a match for the current device
        for i, controller in enumerate(controllers_to_process):
            device_id = controller['DeviceID']

            # Extract the part after the last backslash, which should be the serial
            # Use rsplit with maxsplit=1 for efficiency and correctness
            parts = device_id.rsplit('\\', 1)
            if len(parts) == 2:
                extracted_serial = parts[1]
                # Check if the extracted serial matches the target serial from the device list
                if extracted_serial == target_serial:
                    found_index = i
                    break # Found the controller for this device, stop searching
            # else: If DeviceID format is unexpected (no '\'), it won't match.

        if found_index != -1:
            # If a match was found, remove the controller from the processing list
            # and append it to the sorted list.
            found_controller = controllers_to_process.pop(found_index)
            sorted_controllers.append(found_controller)
        else:
            # This case might indicate an issue if a device doesn't have a corresponding controller
            print(f"Warning: No matching controller found for device serial: {target_serial}")

    # Check if any controllers were left unmatched (should be empty if data is consistent)
    if controllers_to_process:
        print("Warning: Some controllers were not matched and are being appended:")
        pprint(controllers_to_process)
        sorted_controllers.extend(controllers_to_process)
    usb_controllers = sorted_controllers

    # --- Output and Verification ---
    # print("wmi_usb_devices: ")
    # pprint(wmi_usb_devices)
    # print()
    # print("usb_controllers: ")
    # pprint(usb_controllers)
    return usb_controllers

def sort_libusb_data(wmi_usb_devices, libusb_data):
    """
    Sorts libusb_data to align with wmi_usb_devices.
    Includes a pre-check to see if the list is already ordered by PID.
    Current sorting logic uses PID and highest bcdUSB as fallback.
    For more robust sorting, consider implementing logic similar to test.py,
    which uses PID and bcdDevice/REV code matching (requires sorted wmi_usb_drives).
    """
    if not libusb_data:
        # raise UsbTreeError("No libusb_data available to sort") # Or handle appropriately
        return [] # Return empty list or handle error

    # --- Pre-Sort Order Check ---
    is_already_sorted = False
    if len(wmi_usb_devices) == len(libusb_data):
        # Assume sorted until proven otherwise
        potentially_sorted = True
        for i in range(len(wmi_usb_devices)):
            # Compare PID from WMI device with iProduct from libusb entry
            wmi_pid = wmi_usb_devices[i].get('pid')
            libusb_pid = libusb_data[i].get('iProduct')
            if wmi_pid is None or libusb_pid is None or wmi_pid != libusb_pid:
                potentially_sorted = False
                break # Mismatch found, no need to check further
        if potentially_sorted:
            is_already_sorted = True

    if is_already_sorted:
        return libusb_data # Return the list as-is if PIDs align

    # --- Original Sorting Logic (If pre-sort check failed) ---
    print("Info: libusb_data does not appear pre-sorted by PID, proceeding with sorting logic.")

    # Build lookup: {pid: [libusb_entry, ...]}
    pid_map = defaultdict(list)
    for entry in libusb_data:
        # Ensure iProduct exists before adding
        pid_key = entry.get('iProduct')
        if pid_key:
            pid_map[pid_key].append(entry)
        else:
            print(f"Warning: libusb entry missing 'iProduct': {entry}")


    sorted_libusb = []
    # Keep track of used libusb entries using a unique tuple (iProduct, bcdDevice)
    # Initialize used_entries as a set
    used_entries = set()

    for device in wmi_usb_devices:
        pid = device.get('pid')
        if not pid:
            print(f"Warning: WMI device missing 'pid': {device}")
            # Decide how to handle missing PID - skip device, add placeholder?
            # Adding a placeholder for this example
            sorted_libusb.append({
                "iProduct": "UNKNOWN", "bcdDevice": "0000", "bcdUSB": 0.0,
                "bus_number": -1, "dev_address": -1, "error": "Missing WMI PID"
             })
            continue

        candidates = pid_map.get(pid, [])

        if not candidates:
            print(f"Warning: No libusb entry found for PID {pid}")
            sorted_libusb.append({
                "iProduct": pid, "bcdDevice": "0000", "bcdUSB": 0.0,
                "bus_number": -1, "dev_address": -1, "error": "No matching libusb entry"
            })
            continue

        # Find the best candidate NOT already used
        best_candidate = None
        # Sort candidates primarily by bcdUSB descending (as per original logic)
        # to pick the highest USB spec first if multiple unused exist.
        candidates.sort(key=lambda x: x.get('bcdUSB', 0.0), reverse=True)

        for candidate in candidates:
            # Create a unique key for the candidate
            candidate_key = (candidate.get('iProduct'), candidate.get('bcdDevice'))
            # Check if the key exists and is not already used
            if candidate_key[0] is not None and candidate_key[1] is not None and candidate_key not in used_entries:
                best_candidate = candidate
                used_entries.add(candidate_key) # Mark as used
                break # Found an unused candidate

        # If all candidates for this PID were already used, or if no suitable candidate found
        if best_candidate is None:
            # This situation is tricky. The original code implicitly reused entries.
            # A safer approach might be to log a warning and add a placeholder,
            # or fallback to the first candidate if reuse is acceptable.
            # Reverting to original behavior (potential reuse/using first candidate) with a warning:
            if candidates: # If there are candidates, even if used
                 best_candidate = candidates[0] # Fallback to the first one (highest bcdUSB)
                 fallback_key = (best_candidate.get('iProduct'), best_candidate.get('bcdDevice'))
                 if fallback_key[0] is not None and fallback_key[1] is not None:
                      if fallback_key in used_entries:
                           print(f"Warning: Reusing libusb entry for PID {pid} (Key: {fallback_key}). This might indicate duplicate devices or sorting issues.")
                      else:
                           # This case should ideally not happen if logic above is correct, but as a safeguard:
                           used_entries.add(fallback_key)
                 else:
                     # Handle case where the fallback candidate itself lacks key info
                     print(f"Error: Fallback libusb candidate for PID {pid} lacks key information.")
                     best_candidate = { # Add placeholder on error
                         "iProduct": pid, "bcdDevice": "FALLBACK_ERROR", "bcdUSB": 0.0,
                         "bus_number": -1, "dev_address": -1, "error": "Fallback candidate invalid"
                     }
            else:
                 # Should not happen if candidates list was checked earlier, but for safety:
                 best_candidate = { # Add placeholder if truly no candidates
                     "iProduct": pid, "bcdDevice": "NO_CANDIDATES", "bcdUSB": 0.0,
                     "bus_number": -1, "dev_address": -1, "error": "No candidates found (logic error?)"
                 }


        sorted_libusb.append(best_candidate)

    # Final check: Ensure the length matches the input device list
    if len(sorted_libusb) != len(wmi_usb_devices):
        print(f"Error: Length mismatch after sorting libusb data. Expected {len(wmi_usb_devices)}, Got {len(sorted_libusb)}")
        # Depending on requirements, you might raise an error or try to pad/truncate

    libusb_data = sorted_libusb # Assign the sorted list back

    # --- Output (Optional Debugging) ---
    # print("wmi_usb_devices (input order): ")
    # pprint(wmi_usb_devices)
    # print()
    # print("libusb_data (sorted output): ")
    # pprint(libusb_data)
    return libusb_data

def instantiate_class_objects(wmi_usb_devices, wmi_usb_drives, usb_controllers, libusb_data, physical_drives, readonly_map):
    devices = []
    closest_values = {
        "0310": ["Padlock 3.0", [256, 500, 1000, 2000, 4000, 8000, 16000]],
        "0315": ["Padlock DT", [2000, 4000, 6000, 8000, 10000, 12000, 16000, 18000, 20000, 22000, 24000]],
        "0351": ["Aegis Portable", [128, 256, 500, 1000, 2000, 4000, 8000, 12000, 16000]],
        "1400": ["Fortress", [256, 500, 1000, 2000, 4000, 8000, 16000]],
        "1405": ["Padlock SSD", [240, 480, 1000, 2000, 4000]],
        "1406": ["Padlock DT FIPS", [2000, 4000, 6000, 8000, 10000, 12000, 16000, 18000, 20000, 22000, 24000]],
        "1407": ["Secure Key 3.0", [16, 30, 60, 120, 240, 480, 1000, 2000, 4000]],
        "1408": ["Fortress L3", [500, 512, 1000, 2000, 4000, 5000, 8000, 16000, 20000]],
        "1409": ["Secure Key 3.0", [16, 32, 64, 128]],
        "1410": ["Secure Key 3.0", [4, 8, 16, 32, 64, 128, 256, 512]],
        "1413": ["Padlock NVX", [500, 1000, 2000]]}

    # print()
    # print("----------")
    # print("AFTER PROCESSING: ")
    # print("USB Controllers:")
    # pprint(usb_controllers)
    # print()
    # print("wmi_usb_devices:")
    # pprint(wmi_usb_devices)
    # print()
    # print("wmi_usb_drives:")
    # pprint(wmi_usb_drives)
    # print()
    # print("libusb devices:")
    # pprint(libusb_data)
    # print("----------")

    for item in range(len(wmi_usb_devices)):
        idProduct = wmi_usb_devices[item]['pid']
        idVendor = wmi_usb_devices[item]['vid']
        bcdDevice = libusb_data[item]['bcdDevice']
        bcdUSB = libusb_data[item]['bcdUSB']
        iManufacturer = wmi_usb_devices[item]['manufacturer']
        iProduct = wmi_usb_drives[item]['iProduct']
        usbController = usb_controllers[item]['ControllerName']
        bus_number = libusb_data[item]['bus_number']
        dev_address = libusb_data[item]['dev_address']
        mediaType = wmi_usb_drives[item].get('mediaType', 'Unknown')

        if wmi_usb_devices[item]['serial'].startswith('MSFT30'):
            SCSIDevice = True
            iSerial = wmi_usb_devices[item]['serial'][6:]
        else:
            SCSIDevice = False
            iSerial = wmi_usb_devices[item]['serial']

        for key, value in physical_drives.items():
            if key == iSerial:
                drive_number = value

        isReadOnly = readonly_map.get(drive_number, False)

        drive_letter = get_drive_letter_via_ps(drive_number)

        if wmi_usb_drives[item]["size_gb"] == 0.0:
            driveSizeGB = "N/A (OOB Mode)"
        else:
            driveSizeGB = find_closest(wmi_usb_drives[item]["size_gb"], closest_values[idProduct][1])

        # Create device info without usbController for now
        dev_info = WinUsbDeviceInfo(
            bcdUSB=bcdUSB,
            idVendor=idVendor,
            idProduct=idProduct,
            bcdDevice=bcdDevice,
            iManufacturer=iManufacturer,
            iProduct=iProduct,
            iSerial=iSerial,
            SCSIDevice=SCSIDevice,
            driveSizeGB=driveSizeGB,
            usbController=usbController,
            busNumber=bus_number,
            deviceAddress=dev_address,
            physicalDriveNum=drive_number,
            driveLetter=drive_letter,
            mediaType=mediaType,
            readOnly=isReadOnly
        )
        devices.append(dev_info)
    return devices if devices else None

# ==================================
# Main
# ==================================

def find_apricorn_device():
    """
    High-level function tying together WMI USB device data, drive data, and libusb data.
    Returns a list of WinUsbDeviceInfo objects or None if none found.
    """
    wmi_usb_devices = get_wmi_usb_devices()
    wmi_usb_drives = get_wmi_usb_drives()
    usb_controllers = get_all_usb_controller_names()
    libusb_data = get_apricorn_libusb_data()
    physical_drives = get_physical_drive_number()
    readonly_map = get_usb_readonly_status_map()

    wmi_usb_drives = sort_wmi_drives(wmi_usb_devices, wmi_usb_drives)
    usb_controllers = sort_usb_controllers(wmi_usb_devices, usb_controllers)
    libusb_data = sort_libusb_data(wmi_usb_devices, libusb_data)

    apricorn_devices = instantiate_class_objects(wmi_usb_devices, wmi_usb_drives, usb_controllers, libusb_data, physical_drives, readonly_map)
    return apricorn_devices

def main():
    """
    Main function to find and display information about connected Apricorn devices.

    Args:
        find_apricorn_device (callable): A function that returns a list of
                                         macOSUsbDeviceInfo objects representing
                                         connected Apricorn devices.
    """
    devices = find_apricorn_device()
    if devices:
        for idx, dev in enumerate(devices, 1):
            print(f"\n=== Apricorn Device #{idx} ===")
            pprint(vars(dev))
        print()
    else:
        print("No Apricorn devices found.")

if __name__ == '__main__':
    main()
