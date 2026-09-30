import os
import subprocess
import time
import signal
import sys

TIKTOK_URL = os.getenv("TIKTOK_URL", "https://www.tiktok.com/@d.shakertawfiqalaroury/live")
YOUTUBE_RTMP = os.getenv("YOUTUBE_RTMP", "rtmp://a.rtmp.youtube.com/live2/4vm5-3h9h-1t7u-a7aa-0e57")
FACEBOOK_RTMP = os.getenv("FACEBOOK_RTMP", "rtmps://live-api-s.facebook.com:443/rtmp/FB-122144887155180204-0-Ab5tCsVZVVkjdpNVC8cwl3Oa")

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
            "-flvflags", "no_duration_filesize",
            "-f", "flv", YOUTUBE_RTMP,
            "-f", "flv", FACEBOOK_RTMP
        ]

        ffmpeg_process = subprocess.Popen(
            FFMPEG_CMD,
            stdin=streamlink_process.stdout,
            stdout=None,
            stderr=None,
            bufsize=0
        )

        streamlink_process.stdout.close()
        ffmpeg_process.wait()

    except KeyboardInterrupt:
        cleanup()
        break
    except Exception:
        pass
    finally:
        cleanup()

    time.sleep(CHECK_INTERVAL_OFFLINE)
