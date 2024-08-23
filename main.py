import os
import re
import yt_dlp
from typing import List, Dict, Optional, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from youtubesearchpython import VideosSearch
import asyncio

app = FastAPI()

BASE_URL = "https://www.youtube.com/watch?v="
REGEX = r"(?:youtube\.com|youtu\.be)"
LIST_BASE_URL = "https://youtube.com/playlist?list="

class YouTubeAPI:
    def __init__(self):
        self.base = BASE_URL
        self.regex = REGEX
        self.listbase = LIST_BASE_URL

    async def shell_cmd(self, cmd: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stderr:
            if "unavailable videos are hidden" in stderr.decode("utf-8").lower():
                return stdout.decode("utf-8")
            else:
                return stderr.decode("utf-8")
        return stdout.decode("utf-8")

    async def exists(self, link: str, videoid: Optional[bool] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def details(self, link: str, videoid: Optional[bool] = None) -> Dict[str, Union[str, int]]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        results = VideosSearch(link, limit=1)
        result = (await results.next()).get('result', [{}])[0]
        title = result.get("title", "Unknown")
        duration_min = result.get("duration", "0:00")
        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        vidid = result.get("id", "")
        duration_sec = int(self.time_to_seconds(duration_min))
        return {
            "title": title,
            "duration": duration_min,
            "duration_sec": duration_sec,
            "thumbnail": thumbnail,
            "video_id": vidid
        }

    def time_to_seconds(self, duration: str) -> int:
        h, m, s = map(int, re.findall(r'\d+', duration))
        return h * 3600 + m * 60 + s

    async def video(self, link: str, videoid: Optional[bool] = None) -> Union[str, None]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        ydl_opts = {
            "cookies": "cookies.txt",
            "format": "best[height<=?720][width<=?1280]",
            "quiet": True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('url', '')

    async def playlist(self, link: str, limit: int, videoid: Optional[bool] = None) -> List[str]:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        playlist = await self.shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download --cookies cookies.txt {link}"
        )
        return [x for x in playlist.split("\n") if x]

    async def track(self, link: str, videoid: Optional[bool] = None) -> Dict[str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        results = VideosSearch(link, limit=1)
        result = (await results.next()).get('result', [{}])[0]
        title = result.get("title", "Unknown")
        duration_min = result.get("duration", "0:00")
        vidid = result.get("id", "")
        yturl = result.get("link", "")
        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        return {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail
        }

    async def formats(self, link: str, videoid: Optional[bool] = None) -> List[Dict[str, str]]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        ydl_opts = {"quiet": True, "cookiefile": "cookies.txt"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            formats_available = []
            info = ydl.extract_info(link, download=False)
            for format in info.get("formats", []):
                if not "dash" in str(format.get("format", "")).lower():
                    formats_available.append({
                        "format": format.get("format"),
                        "filesize": format.get("filesize"),
                        "format_id": format.get("format_id"),
                        "ext": format.get("ext"),
                        "format_note": format.get("format_note"),
                        "yturl": link
                    })
        return formats_available

    async def slider(self, link: str, query_type: int, videoid: Optional[bool] = None) -> Dict[str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        results = VideosSearch(link, limit=10)
        result = (await results.next()).get('result', [{}])[query_type]
        title = result.get("title", "Unknown")
        duration_min = result.get("duration", "0:00")
        vidid = result.get("id", "")
        thumbnail = result.get("thumbnails", [{}])[0].get("url", "").split("?")[0]
        return {
            "title": title,
            "duration": duration_min,
            "thumbnail": thumbnail,
            "vidid": vidid
        }

    async def download(
        self,
        link: str,
        video: Optional[bool] = False,
        songaudio: Optional[bool] = False,
        songvideo: Optional[bool] = False,
        format_id: Optional[str] = None,
        title: Optional[str] = None
    ) -> str:
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]

        async def audio_dl() -> str:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "cookies.txt",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl.download([link])
                return filepath

        async def video_dl() -> str:
            ydl_opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": "cookies.txt",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                filepath = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(filepath):
                    return filepath
                ydl.download([link])
                return filepath

        async def song_video_dl() -> str:
            formats = f"{format_id}+140"
            filepath = f"downloads/{title}.mp4"
            ydl_opts = {
                "format": formats,
                "outtmpl": filepath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
                "cookiefile": "cookies.txt",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return filepath

        async def song_audio_dl() -> str:
            filepath = f"downloads/{title}.%(ext)s"
            ydl_opts = {
                "format": format_id,
                "outtmpl": filepath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "cookiefile": "cookies.txt",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return filepath

        if songvideo:
            return await song_video_dl()
        elif songaudio:
            return await song_audio_dl()
        elif video:
            return await video_dl()
        else:
            return await audio_dl()

yt_api = YouTubeAPI()

class URLRequest(BaseModel):
    url: str
    format_id: Optional[str] = None
    title: Optional[str] = None
    songaudio: Optional[bool] = False
    songvideo: Optional[bool] = False
    video: Optional[bool] = False

@app.get("/")
async def read_root():
    return {"message": "Web developed by Pragyan"}

@app.post("/fetch")
async def fetch(url_request: URLRequest):
    url = url_request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    details = await yt_api.details(url)
    return details

@app.post("/download")
async def download(url_request: URLRequest):
    url = url_request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    filepath = await yt_api.download(
        url,
        video=url_request.video,
        songaudio=url_request.songaudio,
        songvideo=url_request.songvideo,
        format_id=url_request.format_id,
        title=url_request.title
    )
    return {"file_path": filepath}

# Additional routes can be added here following the same pattern

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
