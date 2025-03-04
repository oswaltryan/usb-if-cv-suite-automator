import json
import shutil

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
