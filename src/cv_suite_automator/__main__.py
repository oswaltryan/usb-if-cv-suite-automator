# src/cv_suite_automator/__main__.py

import sys
from .core import CVSuiteAutomation

def main():
    """
    Main entry point for the CV Suite automation script.
    """
    # Check for the required command-line argument.
    if len(sys.argv) != 2:
        print("ERROR: One argument is required for this program:")
        print("    1 - (str) Bridge Controller Chipset")
        print("Example:")
        print(r'    C:\...\scripts\run_automation.bat "3639EN-FL"')
        # Exit with a non-zero code to indicate failure.
        sys.exit(1)

    # The main execution logic from the original cv_suite_automation.py
    # would go here, wrapped to ensure it returns a status.
    # For now, we will just instantiate the class and let its __init__ run.
    # In a full refactor, the main loop would be here.
    
    # This is a simplified representation of the main loop
    # The actual full loop from your original script should be here
    cv_suite = CVSuiteAutomation()

    # Assuming the main loop and all tests are now run within the
    # CVSuiteAutomation class instance or a method called from it.
    # If the class's methods can fail, they should raise an exception.
    
    # For now, if the script reaches this point without an exception,
    # it is considered a success.
    print("\nPython script completed its tasks successfully.")


if __name__ == "__main__":
    exit_code = 0  # Assume success by default
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        exit_code = 130 # Standard exit code for Ctrl+C
    except Exception as e:
        # Catch any other unexpected exceptions during execution
        print(f"\nFATAL ERROR: An unexpected exception occurred: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        exit_code = 1 # Generic error code
    finally:
        # This block ALWAYS runs, ensuring we always exit with a specific code.
        print(f"Exiting with code: {exit_code}")
        sys.exit(exit_code)