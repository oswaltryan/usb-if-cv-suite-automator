import json
import os
import shutil
from typing import Optional

def encode_with_inline_lists(obj, level=0, indent=4):
    """
    Recursively encodes 'obj' into a JSON string where:
      - Dictionaries are pretty-printed with 'indent' spaces per level.
      - Lists always appear in a single line: [a, b, c].
      - Primitives (strings, numbers, bools) are handled via json.dumps(...).
    """
    # Handle dictionaries with indentation
    if isinstance(obj, dict):
        if not obj:  # empty dict
            return "{}"
        
        # We'll store each "key: value" line here
        items = []
        for key, value in obj.items():
            # Encode the key
            encoded_key = json.dumps(key, ensure_ascii=False)
            
            # Recursively encode the value
            encoded_value = encode_with_inline_lists(value, level + 1, indent)
            
            # Combine into a single line like: "key": value
            line = f'{encoded_key}: {encoded_value}'
            items.append(line)
        
        # Build the dictionary block with newlines and indentation
        current_indent = ' ' * (indent * level)
        child_indent = ' ' * (indent * (level + 1))
        
        # Join items with commas + newlines
        joined_items = ",\n".join(child_indent + item for item in items)
        return "{\n" + joined_items + "\n" + current_indent + "}"

    # Handle lists on a single line
    elif isinstance(obj, list):
        # This is what keeps lists on one line
        return json.dumps(obj, ensure_ascii=False)

    # Otherwise, let json.dumps handle primitives (str, int, bool, None, etc.)
    else:
        return json.dumps(obj, ensure_ascii=False)


def custom_json_dump(data, file_path, indent=4):
    """
    Writes 'data' as JSON to 'file_path', using 'encode_with_inline_lists'
    for the encoding so that lists are inline and dictionaries are indented.
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(encode_with_inline_lists(data, level=0, indent=indent))


# -----------------------
# Example usage
# -----------------------

# # 1. Load the template
# with open('C:\\Users\\itadmin\\Desktop\\cv_suite_testing\\summary_template.json', 'r', encoding='utf-8') as jsonFile:
#     data = json.load(jsonFile)

# # 2. Update or extend lists (these items should appear inline)
# data["Windows 11"]["ASMedia"]["USB3"]["Device Summary"].extend([2, 0])

# # 3. (Optional) backup original
# shutil.copy('C:\\Users\\itadmin\\Desktop\\cv_suite_testing\\summary_template.json', 
#             'C:\\Users\\itadmin\\Desktop\\cv_suite_testing\\new_summary.json')

# # 4. Use custom dump to write the new JSON
# custom_json_dump(data, 'C:\\Users\\itadmin\\Desktop\\cv_suite_testing\\new_summary.json', indent=4)


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

