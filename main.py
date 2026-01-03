import os
import json
import subprocess
import shutil
import re

def sanitize_filename(name):
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def find_bilibili_cache(root_dir):
    """递归查找包含 entry.json 的目录"""
    cache_dirs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if 'entry.json' in filenames:
            cache_dirs.append(dirpath)
    return cache_dirs

def process_cache(cache_dir, output_dir):
    """解析 entry.json 并转换音频"""
    entry_path = os.path.join(cache_dir, 'entry.json')
    try:
        with open(entry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取标题
        title = data.get('title', 'Unknown_Title')
        part_name = data.get('page_data', {}).get('part', '')
        
        full_title = f"{title}_{part_name}" if part_name else title
        full_title = sanitize_filename(full_title)
        
        # 查找音频文件
        # B站缓存通常在 entry.json 同级的子目录里（通常是数字命名的目录，如 '64', '80' 等）
        audio_path = None
        for item in os.listdir(cache_dir):
            item_path = os.path.join(cache_dir, item)
            if os.path.isdir(item_path):
                # 检查常见文件名
                for f in ['audio.m4s', '0.blv']:
                    potential_audio = os.path.join(item_path, f)
                    if os.path.exists(potential_audio):
                        audio_path = potential_audio
                        break
            if audio_path:
                break
        
        if not audio_path:
            print(f"Skipping {cache_dir}: Audio file not found.")
            return

        output_file = os.path.join(output_dir, f"{full_title}.mp3")
        
        # 如果是 .m4s 文件，通常需要去掉前 9 个字节（B站自定义头）
        # 但 ffmpeg 有时能直接识别，或者我们手动处理
        # 简单起见，先尝试直接用 ffmpeg 转换
        
        print(f"Converting: {full_title}")
        
        # 使用 ffmpeg 转换
        cmd = [
            'ffmpeg', '-y',
            '-i', audio_path,
            '-vn', # 不处理视频
            '-acodec', 'libmp3lame',
            '-q:a', '2', # 高质量
            output_file
        ]
        
        # 尝试静默运行 - 指定编码为 utf-8 并忽略错误，防止 Windows GBK 环境崩溃
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if result.returncode != 0:
            # 如果失败，可能是 m4s 的伪影问题，尝试跳过前 9 字节
            if audio_path.endswith('.m4s'):
                temp_audio = "temp_audio.m4s"
                try:
                    with open(audio_path, 'rb') as f_in:
                        f_in.seek(9) # 跳过 B站头
                        with open(temp_audio, 'wb') as f_out:
                            f_out.write(f_in.read())
                    
                    cmd[3] = temp_audio
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    os.remove(temp_audio)
                except Exception as e:
                    print(f"Second attempt failed for {full_title}: {e}")
            
            if result.returncode != 0:
                print(f"Failed to convert {full_title}: {result.stderr}")
            else:
                print(f"Successfully converted: {full_title}")
        else:
            print(f"Successfully converted: {full_title}")

    except Exception as e:
        print(f"Error processing {cache_dir}: {e}")

def check_ffmpeg():
    """检查系统是否安装了 ffmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, encoding='utf-8', errors='ignore')
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    import argparse
    import sys

    # 检查依赖
    if not check_ffmpeg():
        print("错误: 未找到 ffmpeg。")
        print("请确保已安装 FFmpeg 并将其添加到系统环境变量 PATH 中。")
        print("下载地址: https://ffmpeg.org/download.html")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Bilibili Mobile Cache to MP3 Converter")
    parser.add_argument("input", nargs="?", default=".", help="B站缓存根目录 (默认: 当前目录 '.')")
    parser.add_argument("-o", "--output", default="output_mp3", help="MP3输出目录 (默认: 'output_mp3')")
    
    args = parser.parse_args()
    
    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        print(f"错误: 输入路径 '{input_path}' 不存在。")
        sys.exit(1)
    
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path)
            print(f"已创建输出目录: {output_path}")
        except Exception as e:
            print(f"错误: 无法创建输出目录 '{output_path}': {e}")
            sys.exit(1)
    
    print(f"正在扫描目录: {input_path}")
    cache_dirs = find_bilibili_cache(input_path)
    
    if not cache_dirs:
        print("未发现有效的 B 站缓存目录 (未找到 entry.json)。")
        print("请确保您指向的是包含 'download' 文件夹或其子文件夹的目录。")
        return

    print(f"找到 {len(cache_dirs)} 个缓存项目。开始转换...")
    
    count = 0
    for d in cache_dirs:
        process_cache(d, output_path)
        count += 1
    
    print(f"\n处理完成！共转换 {count} 个项目。")
    print(f"输出位置: {output_path}")

if __name__ == "__main__":
    main()
