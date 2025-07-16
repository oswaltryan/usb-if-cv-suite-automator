import os
import platform
from setuptools import setup, find_packages

# Read README for long description if available
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", encoding="utf-8") as f:
        long_description = f.read()

# Only include setup_requires on Windows
setup_requires = []
if platform.system().lower().startswith("win"):
    setup_requires = ["setuptools>=75.8.0"]

setup(
    name='usb-tool',  
    version='0.2.0',
    description='Cross-platform USB tool.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ryan Oswalt',
    author_email='your.email@example.com',
    url='',  # e.g., your GitHub repo
    packages=find_packages(),
    python_requires='>=3.9',

    # Only install Windows deps on Windows
    install_requires=[
        'pywin32==309; platform_system=="Windows"',
        'libusb==1.0.27.post4; platform_system=="Windows"',
        'pygments==2.19.1; platform_system=="Windows"',
    ],

    setup_requires=setup_requires,

    include_package_data=True,

    # Console entry points for main tool and update command:
    entry_points={
        'console_scripts': [
            'usb=usb_tool.cross_usb:main',
            'usb-update=usb_tool.update:main',
        ],
    },

    classifiers=[
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: MIT License',
    ],
)

if platform.system().lower == "linux":
    print()
    print("\033[91m" + "To run, please run 'sudo usb'" + "\033[0m")
    print("\033[91m" + "To run without sudo, run 'sudo ./update_sudoersd.sh'" + "\033[0m")
    print()
