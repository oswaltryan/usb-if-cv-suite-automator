ToDo:

- run_automation.py needs to rm the test_in_progress.flag after IF IT WAS THERE ALREADY
- start_cv_suite_session.py creates a flag and then you see in the terminal output "No suitable recent session to latch onto", remove that string.
- If the device is not found between tests, either restart or re-enumerate the device and pick up from there, right now it prompts the user to continue but it doesn't
- Need to get more specific with the controller selection, specifically to omit the ASM3242
- A check to see if any of the controllers are stuck in 'compliance mode' and then uninstall device if it is.
- There is a bug where the correct device is tested, but the string of the device name grabbed is the Portable. Use the 240GB ASK3-3639 at the bench to troubleshoot.