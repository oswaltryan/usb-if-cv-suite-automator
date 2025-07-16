#!/bin/bash

# Define the source filename and destination directory
source_file="usb_tool_sudoers"
destination="/etc/sudoers.d/"

# Check if the source file exists
if [ ! -f "$source_file" ]; then
  echo "Error: Source file '$source_file' does not exist."
  exit 1
fi

# Check if the destination directory exists
if [ ! -d "$destination" ]; then
  echo "Error: Directory '$destination' does not exist."
  exit 1
fi

# Define the destination filename
destination_file="${destination}$(basename "$source_file")"

# Copy the file to the destination directory
cp "$source_file" "$destination_file"

# Set appropriate permissions (read-only for root)
chmod 0440 "$destination_file"
chown root:root "$destination_file"

echo "File '$(basename "$source_file")' has been copied to '$destination' with root ownership and read-only permissions."
echo "Remember to use 'sudo visudo -f $destination_file' to edit it safely!"

exit 0
