# usb_tool/__init__.py

import platform

if platform.system().lower().startswith("win"):
    from .windows_usb import (
        find_apricorn_device,
        main,
        WinUsbDeviceInfo,
    )
    __all__ = [
        "find_apricorn_device",
        "main",
        "WinUsbDeviceInfo",
    ]
elif platform.system().lower().startswith("darwin"):
    from .mac_usb import (
        find_apricorn_device,
        main,
        macOSUsbDeviceInfo,
    )
    __all__ = [
        "find_apricorn_device",
        "main",
        "WinUsbDeviceInfo",
    ]
else:
    from .linux_usb import (
        find_apricorn_device,
        main,
        LinuxUsbDeviceInfo
    )
    __all__ = [
        "find_apricorn_device",
        "main",
        "LinuxUsbDeviceInfo",
    ]
