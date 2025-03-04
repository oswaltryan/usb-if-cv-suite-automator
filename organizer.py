import os
import shutil
from typing import Optional
#this function could use some refactoring but this is a good scaffold for now, even did some type hinting!!!!

def pull_files(
    source: str,
    dest: str,
    fallback: Optional[str] = None,
    preserve: bool = False,
    verbose: bool = False
) -> None:
    """
    Parameters:
        source (str): The root directory containing the nested folders.
        dest (str): The directory where the `.html` files will be organized.
        fallback (Optional[str]): Fallback directory if the destination is not writable or available.
        preserve (bool): If True, retains folder structure in the destination. Defaults to False
        verbose (bool): If True, prints details of the files being moved. Defaults to False
    """
    #sub function to check that our target directory exists cuz we cooking today
    def ensure_exists(directory: str):
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
                if verbose:
                    print(f"Created directory: {directory}")
        except Exception as e:
            raise OSError(f"Failed to create directory {directory}: {e}")

    # Ensure source directory exists
    if not os.path.exists(source):
        raise ValueError(f"Source directory does not exist: {source}")

    # Check that the directory exists and can be written to with our function above else fallback
    try:
        ensure_exists(dest)
    except OSError as e:
        if fallback:
            print(f"Warning: {e}. Falling back to: {fallback}")
            dest = fallback
            ensure_exists(dest)
        else:
            raise ValueError("Destination directory is unavailable, and no fallback provided.")

    # Iterate through source directory and move files
    for root, _, files in os.walk(source):
        for file in files:
            if file.endswith(".html"):
                try:
                    src_path = os.path.join(root, file)
                    
                    # Handle preserving directory structure else just go to destination directly
                    if preserve:
                        relative_path = os.path.relpath(root, source)
                        dest_path = os.path.join(dest, relative_path)
                        ensure_exists(dest_path)
                        dest_file_path = os.path.join(dest_path, file)
                    else:
                        dest_file_path = os.path.join(dest, file)
                    
                    # Check for duplicates
                    if os.path.exists(dest_file_path):
                        base, ext = os.path.splitext(file)
                        counter = 1
                        while os.path.exists(dest_file_path):
                            dest_file_path = os.path.join(
                                dest,
                                f"{base}_{counter}{ext}"
                            )
                            counter += 1
                    
                    # Declare moving files if verbose
                    if verbose:
                        print(f"Moving {src_path} to {dest_file_path}")
                    shutil.move(src_path, dest_file_path)
                
                except Exception as e:
                    print(f"Error moving file {file}: {e}")


    try:
        # Iterate through the contents of the directory
        for item in os.listdir(source):
            item_path = os.path.join(source, item)
            # Check if the item is a folder
            if os.path.isdir(item_path):
                # Remove the folder and its contents
                shutil.rmtree(item_path)
    except Exception as e:
        print(f"An error occurred deleteing folders from {source}: {e}")



    if verbose:
        print(f"Completed organizing HTML files into: {dest}")


# -----------------------
# Example usage
# -----------------------

# # Parameters
# source = "/path/to/source"
# dest = "/path/to/destination"
# fallback = "/path/to/fallback"

# # # # Organize HTML files
# pull_files(
#     source=source,
#     dest=dest,
#     fallback=fallback,  
#     preserve=False,  
#     verbose=False  
# )
