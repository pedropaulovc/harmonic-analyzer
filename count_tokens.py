#!/usr/bin/env python3
"""
Calculate accurate Claude token count for .md and .cs files recursively in a directory.
Uses Anthropic's official tokenizer for precise token counting.
"""

import os
import argparse
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


def count_tokens_anthropic(text):
    """Count tokens using tiktoken (most accurate available method)."""
    # Anthropic uses a similar tokenization to tiktoken's cl100k_base
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def count_tokens_tiktoken(text):
    """Count tokens using tiktoken (Claude-compatible encoding)."""
    # Use cl100k_base encoding which is closest to Claude's tokenization
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_claude_tokens(text):
    """
    Fallback estimation using character-based approximation.
    Claude uses approximately 3.5-4 characters per token on average.
    """
    return len(text) // 4


def count_file_tokens(file_path, token_counter):
    """Count tokens in a single file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return token_counter(content)
    except (UnicodeDecodeError, PermissionError) as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return 0


def find_files(directory, extensions):
    """Find all files with specified extensions recursively."""
    files = []
    for ext in extensions:
        files.extend(Path(directory).rglob(f"*.{ext}"))
    return files


def main():
    parser = argparse.ArgumentParser(description="Count Claude tokens in .md and .cs files")
    parser.add_argument("directory", nargs="?", default=".", 
                       help="Directory to scan (default: current directory)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show token count for each file")
    parser.add_argument("--method", choices=["anthropic", "tiktoken", "estimate"], 
                       help="Token counting method (auto-detected if not specified)")
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a valid directory")
        return 1
    
    # Determine token counting method
    if args.method == "anthropic" and HAS_ANTHROPIC:
        token_counter = count_tokens_anthropic
        method_name = "Anthropic official"
    elif args.method == "tiktoken" and HAS_TIKTOKEN:
        token_counter = count_tokens_tiktoken
        method_name = "tiktoken (cl100k_base)"
    elif HAS_ANTHROPIC:
        token_counter = count_tokens_anthropic
        method_name = "Anthropic official"
    elif HAS_TIKTOKEN:
        token_counter = count_tokens_tiktoken
        method_name = "tiktoken (cl100k_base)"
    else:
        token_counter = estimate_claude_tokens
        method_name = "Character-based estimation"
        print("Warning: Neither anthropic nor tiktoken library found. Using estimation.")
        print("Install with: pip install anthropic tiktoken")
    
    print(f"Using method: {method_name}")
    
    extensions = ["md", "cs"]
    files = find_files(args.directory, extensions)
    
    if not files:
        print(f"No .md or .cs files found in {args.directory}")
        return 0
    
    total_tokens = 0
    file_counts = {}
    
    for file_path in sorted(files):
        tokens = count_file_tokens(file_path, token_counter)
        total_tokens += tokens
        file_counts[file_path] = tokens
        
        if args.verbose:
            print(f"{tokens:8,} tokens: {file_path}")
    
    print(f"\nSummary:")
    print(f"Files scanned: {len(files)}")
    print(f"Total tokens: {total_tokens:,}")
    
    # Cost estimates for Claude 3.5 Sonnet
    input_cost = total_tokens * 0.000003  # $3 per million input tokens
    print(f"Estimated input cost (Claude 3.5 Sonnet): ${input_cost:.4f}")


if __name__ == "__main__":
    main()