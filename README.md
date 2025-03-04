# Windows Scripting Project

## Overview
The **Windows Scripting Project** is designed to simplify and automate tasks on Windows systems. The project includes various Python scripts and tools for automation, file organization, and testing. It is suitable for developers, testers, and system administrators looking to enhance productivity through scripting.

## Features
- **Automation Scripts:** Includes `cv_suite_automation.py` for streamlined automation tasks.
- **File Organization:** Use `organizer.py` to manage and organize files efficiently.
- **Input Testing:** Validate and test input handling with `input_test.py`.
- **Pre-built Dependencies:** Includes precompiled wheels and source distributions for easy installation.

## Getting Started
### Prerequisites
- Python 3.10 or higher
- pip (Python package installer)

### Installation
1. Clone this repository or download the ZIP file.
2. Extract the contents if downloaded as a ZIP.
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt --find-links=wheels --no-index 
   ```

### Usage
- Run specific scripts for desired tasks:
  - **Automation:**
    ```bash
    python cv_suite_automation.py
    ```
  - **File Organization:**
    ```bash
    python organizer.py
    ```
  - **Input Testing:**
    ```bash
    python input_test.py
    ```

## Project Structure
```
windowscripting/
|-- cv_suite_automation.py       # Automation script
|-- input_test.py                # Input testing script
|-- organizer.py                 # File organizer script
|-- requirements.txt             # Dependencies
|-- setup.py                     # Package setup script
|-- wheels/                      # Precompiled Python packages
|-- __pycache__/                 # Python cache files
|-- your_package_name.egg-info/  # Package metadata
```

## Contributing
Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch:
   ```bash
   git checkout -b feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Description of changes"
   ```
4. Push to your branch:
   ```bash
   git push origin feature-name
   ```
5. Open a Pull Request.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact
For any inquiries, please contact the project maintainer at [roswalt@apricorn.com](mailto:roswalt@apricorn.com).

