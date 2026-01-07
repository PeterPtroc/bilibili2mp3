import os
import json
import subprocess
import shutil
import re
from openai import OpenAI
from mutagen.id3 import ID3, TIT2, TPE1, TALB
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端
client = None
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

def sanitize_filename(name):
    """移除文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', name)

def extract_metadata_with_ai(title):
    """调用 AI 提取歌名和歌手"""
    if not client:
        return None
    
    prompt = f"""
    从以下视频标题中提取歌曲信息。如果标题看起来不像一首歌，请尝试提取最相关的标题和作者。
    请仅以 JSON 格式返回，包含 'title' (歌名) 和 'artist' (歌手) 两个字段。
    如果无法确定，请返回 {{"title": "{title}", "artist": "Unknown"}}。
    
    标题: {title}
    """
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "你是一个音乐元数据提取助手。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"AI metadata extraction failed: {e}")
        return None

def apply_metadata(file_path, metadata):
    """将元数据写入 MP3 文件"""
    if not metadata:
        return
    
    try:
        audio = ID3(file_path)
    except Exception:
        audio = ID3()
        
    try:
        audio.add(TIT2(encoding=3, text=metadata.get('title', '')))
        audio.add(TPE1(encoding=3, text=metadata.get('artist', '')))
        # 如果需要，也可以添加专辑信息等
        if 'album' in metadata:
            audio.add(TALB(encoding=3, text=metadata['album']))
        audio.save(file_path)
        print(f"Applied metadata: {metadata.get('title')} - {metadata.get('artist')}")
    except Exception as e:
        print(f"Failed to apply metadata to {file_path}: {e}")

def find_bilibili_cache(root_dir):
    """递归查找包含 entry.json 的目录"""
    cache_dirs = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if 'entry.json' in filenames:
            cache_dirs.append(dirpath)
    return cache_dirs

def process_cache(cache_dir, output_dir, use_ai=False):
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
        audio_path = None
        for item in os.listdir(cache_dir):
            item_path = os.path.join(cache_dir, item)
            if os.path.isdir(item_path):
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
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        if result.returncode != 0:
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
                return
        
        print(f"Successfully converted: {full_title}")

        # AI 提取元数据并写入
        if use_ai and client:
            print(f"Extracting metadata for: {full_title}...")
            metadata = extract_metadata_with_ai(full_title)
            if metadata:
                apply_metadata(output_file, metadata)
                
                # 基于提取的元数据重命名文件
                new_basename = f"{metadata.get('artist', 'Unknown')} - {metadata.get('title', 'Unknown')}"
                new_basename = sanitize_filename(new_basename)
                new_output_file = os.path.join(output_dir, f"{new_basename}.mp3")
                
                if new_output_file != output_file:
                    # 处理同名冲突
                    counter = 1
                    base_new_output_file = new_output_file
                    while os.path.exists(new_output_file):
                        new_output_file = base_new_output_file.replace(".mp3", f" ({counter}).mp3")
                        counter += 1
                    
                    try:
                        os.rename(output_file, new_output_file)
                        print(f"Renamed: {os.path.basename(output_file)} -> {os.path.basename(new_output_file)}")
                    except Exception as e:
                        print(f"Failed to rename file: {e}")
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

    if not check_ffmpeg():
        print("错误: 未找到 ffmpeg。")
        print("请确保已安装 FFmpeg 并将其添加到系统环境变量 PATH 中。")
        print("下载地址: https://ffmpeg.org/download.html")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Bilibili Mobile Cache to MP3 Converter")
    parser.add_argument("input", nargs="?", default=".", help="B站缓存根目录 (默认: 当前目录 '.')")
    parser.add_argument("-o", "--output", default="output_mp3", help="MP3输出目录 (默认: 'output_mp3')")
    parser.add_argument("--ai", action="store_true", help="启用 AI 自动提取元数据 (需配置 .env)")
    
    args = parser.parse_args()
    
    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        print(f"错误: 输入路径 '{input_path}' 不存在。")
        sys.exit(1)
    
    if not api_key and args.ai:
        print("警告: 未检测到 OPENAI_API_KEY，AI 功能将不可用。请在 .env 文件中配置。")
    
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
        return

    print(f"找到 {len(cache_dirs)} 个缓存项目。开始转换...")
    
    count = 0
    for d in cache_dirs:
        process_cache(d, output_path, use_ai=args.ai)
        count += 1
    
    print(f"\n处理完成！共处理 {count} 个项目。")
    print(f"输出位置: {output_path}")

if __name__ == "__main__":
    main()
