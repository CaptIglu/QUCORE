# -*- coding: utf-8 -*-
import os
import sys
import re

def main():
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py <new_version>")
        sys.exit(1)
        
    new_version = sys.argv[1].strip()
    # Basic validation of SemVer (e.g. 0.6.0)
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print(f"Error: Version '{new_version}' is not a valid semantic version (e.g., 0.6.0).")
        sys.exit(1)
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    metadata_path = os.path.join(script_dir, "metadata.txt")
    plugin_path = os.path.join(script_dir, "plugin.py")
    
    # 1. Update metadata.txt
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_content = f.read()
        
        # Replace version=...
        new_metadata, count = re.subn(r'^version=.*$', f"version={new_version}", metadata_content, flags=re.MULTILINE)
        if count > 0:
            with open(metadata_path, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write(new_metadata)
            print(f"Updated metadata.txt to version {new_version}")
        else:
            print("Warning: 'version=' line not found in metadata.txt")
    else:
        print("Error: metadata.txt not found!")
        sys.exit(1)
        
    # 2. Update plugin.py
    if os.path.exists(plugin_path):
        with open(plugin_path, 'r', encoding='utf-8') as f:
            plugin_content = f.read()
            
        # Replace version = self.metadata.get('version', '...')
        pattern = r"(version\s*=\s*self\.metadata\.get\(\s*['\"]version['\"]\s*,\s*['\"])[^'\"]+(['\"]\s*\))"
        new_plugin, count = re.subn(pattern, r"\g<1>" + new_version + r"\g<2>", plugin_content)
        if count > 0:
            with open(plugin_path, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write(new_plugin)
            print(f"Updated plugin.py fallback version to {new_version}")
        else:
            print("Warning: version fallback pattern not found in plugin.py")
    else:
        print("Error: plugin.py not found!")
        sys.exit(1)
        
    print("Version bump completed successfully!")

if __name__ == "__main__":
    main()
