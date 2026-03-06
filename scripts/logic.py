import json
import urllib.request
import urllib.error
import os
import sys
import subprocess
import time
import shutil
import zipfile
import importlib.util
from datetime import datetime
from typing import List, Optional

# --- 配置 ---
MOJANG_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
# 从环境变量获取目标仓库路径，默认为当前目录下的 target_repo
TARGET_REPO_PATH = os.environ.get('TARGET_REPO_PATH', './target_repo')
VERSION_FILE = os.path.join(TARGET_REPO_PATH, 'version.txt')

# 脚本所在目录 (用于寻找 versions.properties 和 LatestNeoForm.py)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROPERTIES_FILE = os.path.join(SCRIPT_DIR, '..', 'versions.properties')

_version_cache: Optional[List[dict]] = None

_DEBUG = False

def _fetch_manifest() -> List[dict]:
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    
    req = urllib.request.Request(MOJANG_MANIFEST_URL)
    req.add_header('User-Agent', 'COVID-Trump/fluffy-spoon/1')
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        _version_cache = data.get('versions', [])
    return _version_cache

def _get_version_time(vid: str, manifest: List[dict]) -> Optional[datetime]:
    for v in manifest:
        if v.get('id') == vid:
            if _DEBUG: print('{ts=}')
            ts = v.get('releaseTime')
            if ts:
                if ts.endswith('Z'): ts = ts[:-1] + '+00:00'
                return datetime.fromisoformat(ts)
    return None

def list_mc_versions(_from: Optional[str], _to: Optional[str], releases_only: bool = False) -> List[str]:
    manifest = _fetch_manifest()
    from_time = _get_version_time(_from, manifest) if _from else None
    to_time = _get_version_time(_to, manifest) if _to else None
    if _DEBUG: print(f'{from_time=} {to_time=}')
    
    candidates = []
    for v in manifest:
        vid = v.get('id')
        vtype = v.get('type')
        ts_str = v.get('releaseTime')
        
        if not vid or not ts_str: continue
        if releases_only and vtype != 'release': continue
        
        try:
            if ts_str.endswith('Z'): ts_str = ts_str[:-1] + '+00:00'
            vtime = datetime.fromisoformat(ts_str)
        except ValueError: continue
        
        if from_time and vtime < from_time: continue
        if to_time and vtime > to_time: continue
        
        candidates.append({'id': vid, 'time': vtime})
    
    candidates.sort(key=lambda x: x['time'])
    return [x['id'] for x in candidates]

def get_last_processed_version() -> Optional[str]:
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            ver = f.read().strip()
            if ver: return ver
    return None

def parse_properties(path: str) -> dict:
    props = {}
    if not os.path.exists(path):
        if _DEBUG: print(f'os.path.not_exists({path})')
        return props
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if '=' in line:
                k, v = line.split('=', 1)
                props[k.strip()] = v.strip()
    if _DEBUG: print(f'{props=}')
    return props

def run_command(cmd: list, cwd=None):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=cwd, capture_output=True)

def process_version(version: str, work_dir: str):
    print(f"\n=== Processing {version} ===")
    
    # 1. 获取 NeoForm 版本
    lnf_path = os.path.join(SCRIPT_DIR, 'LatestNeoForm.py')
    try:
        result = subprocess.run(
            ['python3', lnf_path, version], 
            capture_output=True, text=True, check=True, cwd=work_dir
        )
        neoform_ver = result.stdout.strip()
    except Exception as e:
        print(f"Failed to get NeoForm version: {e}")
        sys.exit(1)

    print(f"Using NeoForm: {neoform_ver}")

    # 2. 运行 nfrt
    # 注意：请根据 nfrt 实际参数调整。这里假设 version 需要通过 --version 传入
    cmd = [
        'java', '-jar', os.path.join(work_dir, 'nfrt.jar'), 'run',
        '--dist=joined',
        '--neoform', f'net.neoforged:neoform:{neoform_ver}@zip',
        '--write-result', "gameSources:" + os.path.join(work_dir, 'src.zip')
    ]
    
    run_command(cmd, cwd=work_dir)
    
    src_zip = os.path.join(work_dir, 'src.zip')
    if not os.path.exists(src_zip):
        raise Exception("src.zip not generated!")

    # 3. 解压到 target_repo
    target_dir = TARGET_REPO_PATH
    
    # 清理 target_dir (保留 .git 和 version.txt)
    if os.path.exists(target_dir):
        for item in os.listdir(target_dir):
            if item == '.git' or item == 'version.txt':
                continue
            path = os.path.join(target_dir, item)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    else:
        os.makedirs(target_dir)
            
    with zipfile.ZipFile(src_zip, 'r') as zip_ref:
        zip_ref.extractall(target_dir)
        
    # 4. 更新 version.txt
    with open(VERSION_FILE, 'w') as f:
        f.write(version)
        
    # 5. Git 操作
    os.chdir(target_dir)
    run_command(['git', 'add', '-A'])
    
    status = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    if not status.stdout.strip():
        print("No changes to commit.")
        # 即使没变化也要更新 tag? 通常不需要，但如果想标记进度可以强制打 tag
        # 这里选择跳过
        os.chdir(work_dir)
        return

    run_command(['git', 'commit', '-m', f'Decompiled Minecraft {version}'])
    run_command(['git', 'tag', f'mc-{version}'])
    
    # 清理 src.zip 节省空间
    os.remove(src_zip)
    os.chdir(work_dir)

def push_changes():
    os.chdir(TARGET_REPO_PATH)
    print("Pushing changes...")
    run_command(['git', 'push', 'origin', 'main', '--tags'])
    print("Push successful.")

def main():
    start_time = time.time()
    LIMIT_WARN = 4 * 3600  # 4 hours
    LIMIT_HARD = 4.5 * 3600 # 4.5 hours
    
    work_dir = os.getcwd() # Workflow 运行的工作目录

    # 1. 读取配置
    props = parse_properties(PROPERTIES_FILE)
    min_ver_cfg = props.get('min_version')
    max_ver_cfg = props.get('max_version')
    
    # 2. 确定实际起始版本
    last_ver = get_last_processed_version()
    manifest = _fetch_manifest()
    
    effective_min = min_ver_cfg
    
    if last_ver:
        last_time = _get_version_time(last_ver, manifest)
        cfg_time = _get_version_time(min_ver_cfg, manifest) if min_ver_cfg else None
        
        if last_time:
            if cfg_time is None or last_time > cfg_time:
                effective_min = last_ver
                print(f"Resuming from {last_ver} (newer than config min)")
            else:
                print(f"Starting from config min {min_ver_cfg}")
        else:
            print(f"Last version {last_ver} not found in manifest, ignoring.")
    
    if not effective_min and not max_ver_cfg:
        # 如果都没设置，可能需要全量？或者报错。这里假设至少有一个边界
        # 如果 effective_min 为空，list_mc_versions 会从最早开始
        pass

    # 3. 获取候选列表
    candidates = list_mc_versions(effective_min, max_ver_cfg, releases_only=False)
    
    if not candidates:
        print("No versions to process.")
        return

    print(f"Found {len(candidates)} candidates.")

    # 4. 迭代处理
    for i, version in enumerate(candidates):
        elapsed = time.time() - start_time
        
        # 硬限制检查 (在处理新版本前)
        if elapsed > LIMIT_HARD:
            print("!!! HARD TIME LIMIT REACHED. FORCING EXIT AND PUSH !!!")
            push_changes()
            sys.exit(0)
        
        # 软限制检查
        if elapsed > LIMIT_WARN:
            print("!!! SOFT TIME LIMIT REACHED. Will stop after this version. !!!")
            process_version(version, work_dir)
            push_changes()
            print("Stopped due to time limit.")
            sys.exit(0)

        # 跳过已处理的版本
        if version == effective_min and last_ver == effective_min:
            print(f"Skipping {version} (already processed).")
            continue
            
        process_version(version, work_dir)

    # 正常结束
    push_changes()

if __name__ == '__main__':
    main()
