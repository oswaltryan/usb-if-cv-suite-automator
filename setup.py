from setuptools import setup, find_packages

setup(
    name="your_package_name",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A description of your package",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/your-repo",  # Replace with your repo URL
    packages=find_packages(),
    install_requires=[
        "pywinauto",
        "pyautogui",
        # Add other dependencies here if needed
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
)