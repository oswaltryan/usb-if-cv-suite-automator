# /setup.py

from setuptools import setup, find_packages

# Read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="cv_suite_automator",
    version="0.2.0",
    author="Your Name",  # Replace with your name/team
    author_email="your.email@example.com",
    description="Automated USB-IF compliance testing using the CV Suite application.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/cv_suite_testing",  # Replace with your repo URL
    
    # Tell setuptools where to find the package
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    
    # This is the key change: list only direct dependencies
    install_requires=[
        "pywinauto>=0.6.8",
        "Phidget22",
        "pyautogui",
    ],
    
    # This tells setuptools to include non-Python files like summary_template.json
    include_package_data=True,

    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
        "License :: OSI Approved :: MIT License", # Choose your license
        "Topic :: Software Development :: Testing",
    ],
    python_requires=">=3.12",

    # This makes the package executable via `python -m cv_suite_automator`
    # It requires the __main__.py file to exist.
    entry_points={
        "console_scripts": [
            "run-cv-automation=cv_suite_automator.__main__:main",
        ]
    },
)