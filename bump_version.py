# -*- coding: utf-8 -*-
import os
import sys
import re

def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print("Usage: python bump_version.py <new_version>")
        print("\nDescription:")
        print("  Updates the version number in metadata.txt and info_dialogs.py")
        print("  to the specified semantic version (e.g. 0.7.2).")
        sys.exit(0)

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
        
    info_dialogs_path = os.path.join(script_dir, "info_dialogs.py")
    
    # 2. Update info_dialogs.py
    if os.path.exists(info_dialogs_path):
        with open(info_dialogs_path, 'r', encoding='utf-8') as f:
            dialogs_content = f.read()
            
        # Replace version = self.metadata.get('version', '...')
        pattern = r"(version\s*=\s*self\.metadata\.get\(\s*['\"]version['\"]\s*,\s*['\"])[^'\"]+(['\"]\s*\))"
        new_dialogs, count = re.subn(pattern, r"\g<1>" + new_version + r"\g<2>", dialogs_content)
        if count > 0:
            with open(info_dialogs_path, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write(new_dialogs)
            print(f"Updated info_dialogs.py fallback version to {new_version}")
        else:
            print("Warning: version fallback pattern not found in info_dialogs.py")
    # 3. Update architecture.md
    arch_path = os.path.join(script_dir, "architecture.md")
    if os.path.exists(arch_path):
        with open(arch_path, 'r', encoding='utf-8') as f:
            arch_content = f.read()
        new_arch, count = re.subn(r"Architecture Analysis \(v\d+\.\d+\.\d+\)", f"Architecture Analysis (v{new_version})", arch_content)
        if count > 0:
            with open(arch_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(new_arch)
            print(f"Updated architecture.md to version v{new_version}")
        else:
            print("Warning: Architecture Analysis pattern not found in architecture.md")

    print("Version bump completed successfully!")

if __name__ == "__main__":
    main()

