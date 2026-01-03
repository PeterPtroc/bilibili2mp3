# Bilibili Cache to MP3 Converter

将手机 B 站缓存的视频转换为 MP3 音频文件

主要是给喜欢把B站缓存拿来听歌的人用的（比如我）

## 功能
- 自动扫描 B 站缓存文件夹
- 从entry.json提取视频标题和分集名称作为文件名
- 处理.m4s文件的B站自定义文件头

## 依赖
- python
- ffmpeg(记得添加到PATH)

## 使用方法
1.  将手机上的 B 站缓存目录复制到电脑上（一般在`\Android\data\tv.danmaku.bili\download`）。

2. 直接运行即可（会扫描当前目录，默认输出到`output_mp3`）
    ```bash
    python main.py
    ```
也可以：
    ```bash
    python main.py <您的缓存目录路径> -o <输出目录名>
    ```
