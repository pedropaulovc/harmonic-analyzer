#!/usr/bin/env python3
"""Test all KCL examples from kcl-guide-for-llm.md"""

import re
import subprocess
import tempfile
from pathlib import Path

def extract_kcl_examples(md_file):
    """Extract all KCL code blocks from markdown file"""
    content = Path(md_file).read_text(encoding='utf-8')

    # Find all code blocks marked as kcl
    pattern = r'```kcl\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)

    return matches

def test_kcl_code(code, example_num):
    """Test a single KCL code snippet"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kcl', delete=False, encoding='utf-8') as f:
        f.write(code)
        temp_file = f.name

    try:
        # Try to format the code - this will catch syntax errors
        result = subprocess.run(
            ['zoo', 'kcl', 'format', temp_file],
            capture_output=True,
            text=True,
            timeout=10
        )

        success = result.returncode == 0
        error_msg = result.stderr if not success else None

        return success, error_msg, temp_file
    except subprocess.TimeoutExpired:
        return False, "Timeout expired", temp_file
    except Exception as e:
        return False, str(e), temp_file

def main():
    md_file = 'kcl-guide-for-llm.md'

    print(f"Extracting examples from {md_file}...")
    examples = extract_kcl_examples(md_file)

    print(f"Found {len(examples)} KCL code examples\n")

    passed = 0
    failed = 0
    failures = []

    for i, code in enumerate(examples, 1):
        # Skip empty examples
        if not code.strip():
            continue

        success, error, temp_file = test_kcl_code(code, i)

        if success:
            passed += 1
            print(f"[OK] Example {i}: PASS")
        else:
            failed += 1
            print(f"[FAIL] Example {i}: FAIL")
            failures.append({
                'num': i,
                'code': code[:100] + ('...' if len(code) > 100 else ''),
                'error': error,
                'file': temp_file
            })

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} total")
    print(f"{'='*60}\n")

    if failures:
        print("Failed examples:\n")
        for failure in failures:
            print(f"Example {failure['num']}:")
            print(f"  Code: {failure['code']}")
            print(f"  Error: {failure['error']}")
            print(f"  File: {failure['file']}")
            print()

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    exit(main())
