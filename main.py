import os
import subprocess
import time
import signal
import sys
import requests

TIKTOK_URL = os.getenv("TIKTOK_URL", "https://www.tiktok.com/@d.shakertawfiqalaroury/live")
YOUTUBE_RTMP = os.getenv("YOUTUBE_RTMP", "rtmp://a.rtmp.youtube.com/live2/4vm5-3h9h-1t7u-a7aa-0e57")
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "936215912907900")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN", "EAAWGKbwE7zsBSsSZBFMeooVjWdOdf3rcnYb7B6Ff6OjH4aW3mrPuYf1Dy6HHiuWhkOQXM7ZB7ZA4dIspuhQRDIWC214tCou6xKQjjNDYezh6xhW50RtU67z2fFwAonTke2VycYFHXWT1VyvVyYikx3ZAKHa1KgzJpYhQR7nGoaMFlu3tNjc6yptoqJffm1L0RxUs90CpfVGyvNRENBbJy9v2xXqAxoVKRcPZCHLv88M4JhkBwqoTgADD1aQjO1xFz7oXhf6Y1tyISasgZD")

CHECK_INTERVAL_OFFLINE = int(os.getenv("CHECK_INTERVAL_OFFLINE", "30"))

STREAMLINK_CMD = [
    "streamlink",
    "--hls-live-edge", "2",
    "--ringbuffer-size", "512M",
    "--retry-streams", "2",
    "--retry-max", "2",
    "--stream-segment-attempts", "5",
    "--stream-segment-timeout", "15",
    "--stream-timeout", "30",
    "--stdout",
    TIKTOK_URL,
    "best"
]

streamlink_process = None
ffmpeg_process = None

def create_facebook_live_event():
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/live_videos"
    payload = {
        'access_token': FB_ACCESS_TOKEN,
        'status': 'UNPUBLISHED',
        'title': 'فتاوى وحوار مع مخالفين || الشيخ الدكتور شاكر توفيق العاروري',
        'description': 'حياكم الله أهل السنة والجماعة في بث الدكتور شاكر توفيق العاروري؛ الباحث والمحاضر الأكاديمي المتخصص في علوم الحديث الشريف، والمدير السابق بوزارة الأوقاف الأردنية ومساعد مدير المسجد الأقصى. يهدف هذا البث للإجابة عن أسئلتكم وفتاويكم، وتقديم حوارات ونقاشات علمية هادئة مع المخالفين (من الشيعة، والأشاعرة، والمعتزلة، والمسيحيين، والملحدين، ومنكري السنة)، لنشر منهج الوسطية والدفاع عن سنة النبي صلى الله عليه وسلم.'
    }
    try:
        response = requests.post(url, data=payload)
        data = response.json()
        if 'stream_url' in data:
            return data['id'], data['stream_url']
        return None, None
    except Exception:
        return None, None

def start_facebook_live_event(live_video_id):
    url = f"https://graph.facebook.com/v18.0/{live_video_id}"
    payload = {
        'access_token': FB_ACCESS_TOKEN,
        'end_live_video': False
    }
    try:
        requests.post(url, data=payload)
    except Exception:
        pass

def stop_process(process):
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=3)
            except Exception:
                pass

def cleanup():
    global streamlink_process, ffmpeg_process
    stop_process(ffmpeg_process)
    stop_process(streamlink_process)
    streamlink_process = None
    ffmpeg_process = None

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

while True:
    try:
        cleanup()
        
        streamlink_process = subprocess.Popen(
            STREAMLINK_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )

        time.sleep(3)
        
        if streamlink_process.poll() is not None:
            cleanup()
            time.sleep(CHECK_INTERVAL_OFFLINE)
            continue

        fb_video_id, fb_stream_url = create_facebook_live_event()

        if not fb_stream_url:
            fb_targets = ["-f", "flv", YOUTUBE_RTMP]
        else:
            fb_targets = ["-f", "flv", YOUTUBE_RTMP, "-f", "flv", fb_stream_url]

        FFMPEG_CMD = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-stats",
            "-dts_delta_threshold", "1",
            "-fflags", "+genpts+discardcorrupt",
            "-err_detect", "ignore_err",
            "-thread_queue_size", "1024",
            "-i", "-",
            "-map", "0:v:0", "-c:v", "copy",
            "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
            "-fps_mode", "passthrough",
            "-flush_packets", "1",
            "-flvflags", "no_duration_filesize"
        ] + fb_targets

        ffmpeg_process = subprocess.Popen(
            FFMPEG_CMD,
            stdin=streamlink_process.stdout,
            stdout=None,
            stderr=None,
            bufsize=0
        )

        streamlink_process.stdout.close()

        if fb_video_id:
            time.sleep(5)
            start_facebook_live_event(fb_video_id)

        ffmpeg_process.wait()

    except KeyboardInterrupt:
        cleanup()
        break
    except Exception:
        pass
    finally:
        cleanup()

    time.sleep(CHECK_INTERVAL_OFFLINE)
