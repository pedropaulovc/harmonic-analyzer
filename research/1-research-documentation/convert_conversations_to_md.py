#!/usr/bin/env python3
"""
Convert ChatGPT conversation JSON export to markdown files.
Each conversation thread becomes a separate markdown file.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

def clean_filename(text: str) -> str:
    """Convert text to a safe filename."""
    # Remove or replace unsafe characters
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    # Limit length and strip whitespace
    text = text.strip()[:100]
    # Remove multiple underscores
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

def format_timestamp(timestamp: Optional[float]) -> str:
    """Format timestamp to readable string."""
    if timestamp is None:
        return "Unknown time"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

def extract_conversation_threads(mapping: Dict[str, Any]) -> List[List[str]]:
    """Extract conversation threads from the mapping structure."""
    threads = []
    
    # Find root nodes (nodes with no parent or parent is client-created-root)
    root_nodes = []
    for node_id, node in mapping.items():
        parent = node.get('parent')
        if parent is None or parent == 'client-created-root':
            if node.get('message') is not None:  # Skip client-created-root itself
                root_nodes.append(node_id)
    
    # For each root, follow the conversation thread
    for root_id in root_nodes:
        thread = []
        current_id = root_id
        
        while current_id and current_id in mapping:
            thread.append(current_id)
            # Follow the first child (main conversation path)
            children = mapping[current_id].get('children', [])
            current_id = children[0] if children else None
        
        if thread:
            threads.append(thread)
    
    return threads

def convert_message_to_markdown(node: Dict[str, Any]) -> str:
    """Convert a single message node to markdown."""
    message = node.get('message')
    if not message:
        return ""
    
    author = message.get('author', {})
    role = author.get('role', 'unknown')
    name = author.get('name') or role.title()
    
    content = message.get('content', {})
    content_type = content.get('content_type', '')
    
    create_time = format_timestamp(message.get('create_time'))
    
    # Header
    md = f"## {name}\n"
    md += f"*{create_time}*\n\n"
    
    # Content based on type
    if content_type == 'text':
        parts = content.get('parts', [])
        for part in parts:
            md += f"{part}\n\n"
    
    elif content_type == 'tool_result':
        result = content.get('result', '')
        summary = content.get('summary', '')
        md += f"**Tool Result:**\n```\n{result}\n```\n\n"
        if summary:
            md += f"**Summary:** {summary}\n\n"
    
    elif content_type == 'tether_browsing_display':
        url = content.get('url', '')
        title = content.get('title', '')
        domain = content.get('domain', '')
        text = content.get('text', '')
        
        md += f"**Web Content from {domain}**\n"
        md += f"**Title:** {title}\n"
        md += f"**URL:** {url}\n\n"
        md += f"{text}\n\n"
    
    else:
        # Unknown content type, dump as JSON
        md += f"**Content ({content_type}):**\n```json\n{json.dumps(content, indent=2)}\n```\n\n"
    
    return md

def convert_conversation_to_markdown(thread: List[str], mapping: Dict[str, Any], title: str) -> str:
    """Convert a conversation thread to markdown."""
    md = f"# {title}\n\n"
    
    for node_id in thread:
        if node_id in mapping:
            node_md = convert_message_to_markdown(mapping[node_id])
            if node_md:
                md += node_md + "---\n\n"
    
    return md

def main():
    input_file = '/home/pedropaulovc/src/harmonic-analyzer/research/harmonic-analyzer-conversations.json'
    output_dir = '/home/pedropaulovc/src/harmonic-analyzer/research/conversations_md'
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Read and parse JSON objects
    conversations = []
    
    try:
        with open(input_file, 'r') as f:
            decoder = json.JSONDecoder()
            buffer = f.read()
            idx = 0
            
            while idx < len(buffer):
                buffer = buffer[idx:].lstrip()
                if not buffer:
                    break
                
                try:
                    obj, end_idx = decoder.raw_decode(buffer)
                    idx = end_idx
                    conversations.append(obj)
                except json.JSONDecodeError:
                    # Skip invalid JSON and try to find next valid object
                    idx += 1
    
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    print(f"Found {len(conversations)} conversation objects")
    
    # Process each conversation
    for i, conv in enumerate(conversations):
        title = conv.get('title', f'Conversation {i+1}')
        mapping = conv.get('mapping', {})
        
        if not mapping:
            continue
        
        # Extract conversation threads
        threads = extract_conversation_threads(mapping)
        
        if not threads:
            continue
        
        # Convert main thread (usually the longest one)
        main_thread = max(threads, key=len) if threads else []
        
        if main_thread:
            markdown = convert_conversation_to_markdown(main_thread, mapping, title)
            
            # Create filename
            safe_title = clean_filename(title)
            filename = f"{i+1:03d}_{safe_title}.md"
            filepath = os.path.join(output_dir, filename)
            
            # Write markdown file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"Created: {filename}")

if __name__ == '__main__':
    main()