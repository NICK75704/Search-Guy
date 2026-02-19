# chunk.py
import json
import os
import re
import sys
from datetime import datetime

def parse_timestamp(timestamp_str):
    """
    Parse timestamp string into datetime object.
    
    Args:
        timestamp_str (str): Timestamp in format [YYYY-MM-DD HH:MM:SS UTC]
    
    Returns:
        datetime: Parsed datetime object
    """
    # Remove brackets and parse
    timestamp_str = timestamp_str.strip('[]')
    return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S UTC')

def group_messages_by_time(messages, time_window_minutes=5):
    """
    Group messages that occurred within the same time window together.
    
    Args:
        messages (list): List of message objects with timestamp and content
        time_window_minutes (int): Time window in minutes to group messages
    
    Returns:
        list: List of grouped message objects
    """
    if not messages:
        return []
    
    # Sort messages by timestamp, putting None timestamps at the end
    def sort_key(message):
        timestamp = message['timestamp']
        # Return a tuple where the first element is the timestamp (or max datetime if None)
        # and the second is a fallback to ensure consistent sorting
        if timestamp is None:
            return (datetime.max, message.get('line_number', 0))
        return (timestamp, message.get('line_number', 0))
    
    messages.sort(key=sort_key)
    
    grouped_messages = []
    current_group = [messages[0]]
    current_timestamp = messages[0]['timestamp']
    
    for message in messages[1:]:
        message_timestamp = message['timestamp']
        
        # If current message has no timestamp, create a new group
        if message_timestamp is None:
            # Save current group if it exists
            if current_group:
                grouped_messages.append({
                    'timestamp': current_timestamp,
                    'messages': current_group,
                    'source_file': messages[0]['source_file']
                })
            # Start new group with this message
            current_group = [message]
            current_timestamp = message_timestamp
            continue
        
        # If previous message had no timestamp, start new group
        if current_timestamp is None:
            grouped_messages.append({
                'timestamp': current_timestamp,
                'messages': current_group,
                'source_file': messages[0]['source_file']
            })
            current_group = [message]
            current_timestamp = message_timestamp
            continue
        
        # Calculate time difference
        time_diff = abs((message_timestamp - current_timestamp).total_seconds() / 60)
        
        # If within time window, add to current group
        if time_diff <= time_window_minutes:
            current_group.append(message)
        else:
            # Save current group and start new one
            grouped_messages.append({
                'timestamp': current_timestamp,
                'messages': current_group,
                'source_file': messages[0]['source_file']
            })
            current_group = [message]
            current_timestamp = message_timestamp
    
    # Add the last group
    if current_group:
        grouped_messages.append({
            'timestamp': current_timestamp,
            'messages': current_group,
            'source_file': messages[0]['source_file']
        })
    
    return grouped_messages

def chunk_lines_to_json(input_file_path, output_file_path=None, time_window_minutes=5):
    """
    Read lines from a text file and convert messages into JSON objects
    grouped by similar timestamps.
    
    Args:
        input_file_path (str): Path to the input text file
        output_file_path (str): Path to the output JSON file (optional)
        time_window_minutes (int): Time window in minutes to group messages
    """
    # Get the filename without path
    filename = os.path.basename(input_file_path)
    
    # Read all lines from the input file
    with open(input_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Parse messages with timestamps
    messages = []
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
            
        # Match timestamp pattern [YYYY-MM-DD HH:MM:SS UTC] [username]: message content
        timestamp_pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\] \[(.*?)\]: (.*)'
        match = re.match(timestamp_pattern, line)
        
        if match:
            timestamp_str, username, content = match.groups()
            try:
                timestamp = parse_timestamp(timestamp_str)
                message_obj = {
                    "line_number": line_num,
                    "timestamp": timestamp,
                    "username": username,
                    "content": content,
                    "source_file": filename
                }
                messages.append(message_obj)
            except ValueError as e:
                print(f"Warning: Could not parse timestamp in line {line_num}: {e}")
        else:
            # If line doesn't match timestamp pattern, treat as a standalone message
            message_obj = {
                "line_number": line_num,
                "timestamp": None,
                "username": None,
                "content": line,
                "source_file": filename
            }
            messages.append(message_obj)
    
    # Group messages by time
    grouped_messages = group_messages_by_time(messages, time_window_minutes)
    
    # Determine output file path if not provided
    if output_file_path is None:
        # Create output filename based on input filename
        name_without_ext = os.path.splitext(filename)[0]
        output_file_path = f"{name_without_ext}_grouped_chunks.json"
    
    # Ensure discord_jsons directory exists
    output_dir = "discord_jsons"
    os.makedirs(output_dir, exist_ok=True)
    
    # Full path for the output file
    full_output_path = os.path.join(output_dir, output_file_path)
    
    # Write to JSON file
    with open(full_output_path, 'w', encoding='utf-8') as json_file:
        json.dump(grouped_messages, json_file, indent=2, ensure_ascii=False, default=str)
    
    print(f"Successfully processed {len(messages)} messages from '{filename}'")
    print(f"Grouped into {len(grouped_messages)} time groups")
    print(f"Output saved to '{full_output_path}'")

def process_directory(directory_path, time_window_minutes=5):
    """
    Process all .txt files in the given directory.
    
    Args:
        directory_path (str): Path to the directory containing text files
        time_window_minutes (int): Time window in minutes to group messages
    """
    # Check if directory exists
    if not os.path.exists(directory_path):
        print(f"Error: Directory '{directory_path}' not found.")
        return
    
    # Get all .txt files in the directory
    txt_files = [f for f in os.listdir(directory_path) if f.endswith('.txt') and os.path.isfile(os.path.join(directory_path, f))]
    
    if not txt_files:
        print(f"No .txt files found in '{directory_path}'")
        return
    
    print(f"Found {len(txt_files)} text files to process:")
    for txt_file in txt_files:
        print(f"  - {txt_file}")
    
    # Process each text file
    for txt_file in txt_files:
        input_file_path = os.path.join(directory_path, txt_file)
        try:
            chunk_lines_to_json(input_file_path, time_window_minutes=time_window_minutes)
        except Exception as e:
            print(f"Error processing '{txt_file}': {e}")

def main():
    # Default directory path
    directory_path = "discord_exports/KSU Motorsports"
    time_window_minutes = 5
    
    # Check if arguments were provided
    if len(sys.argv) > 1:
        directory_path = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            time_window_minutes = int(sys.argv[2])
        except ValueError:
            print("Warning: Invalid time window value. Using default of 5 minutes.")
    
    # Process all text files in the directory
    process_directory(directory_path, time_window_minutes)

if __name__ == "__main__":
    main()