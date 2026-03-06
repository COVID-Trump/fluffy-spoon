#!/usr/bin/env python3
import sys
import json
import re
import urllib.request
import urllib.error

_SUFFIX_PATTERN = re.compile(r"^-(\d+)(?:\.(\d+))?$")

def get_latest(base_version: str, versions):
    if not base_version or not versions:
        raise ValueError("Invalid input")
    
    # Special case
    if base_version == '1.21.11':
        base_version = '1.21.11_unobfuscated'   # We want the parameter & local variable table

    best_version = None
    best_parts = None
    prefix = f"{base_version}-"

    for version in versions:
        if not version or not version.startswith(prefix):
            continue
        
        suffix = version[len(prefix):]
        match = _SUFFIX_PATTERN.match(suffix)
        
        if not match:
            continue
        
        try:
            part1 = int(match.group(1))
            part2_str = match.group(2)
            has_part2 = part2_str is not None
            part2 = int(part2_str) if has_part2 else 0
            
            current_parts = (part1, part2, has_part2)
            
            if best_version is None:
                best_version = version
                best_parts = current_parts
            else:
                b_part1, b_part2, b_has_part2 = best_parts
                c_part1, c_part2, c_has_part2 = current_parts
                is_newer = False
                
                if c_part1 > b_part1:
                    is_newer = True
                elif c_part1 == b_part1:
                    if c_has_part2 == b_has_part2:
                        if c_has_part2 and c_part2 > b_part2:
                            is_newer = True
                    elif not c_has_part2 and b_has_part2:
                        is_newer = True
                
                if is_newer:
                    best_version = version
                    best_parts = current_parts
        except ValueError:
            continue

    if best_version is None:
        raise ValueError(f"No valid version found for {base_version}")
    
    return best_version

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 LatestNeoForm.py <minecraft_version>", file=sys.stderr)
        sys.exit(1)

    minecraft_version = sys.argv[1]
    api_url = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoform/"

    try:
        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', 'Python-NeoForm-Latest-Script')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise Exception(f"API status {response.status}")
            
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            
            if not isinstance(json_data, dict) or 'versions' not in json_data:
                raise Exception("Invalid JSON structure")
            
            versions_list = json_data['versions']
            if not isinstance(versions_list, list):
                raise Exception("'versions' is not a list")

            latest = get_latest(minecraft_version, versions_list)
            print(latest)
            
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network Error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
