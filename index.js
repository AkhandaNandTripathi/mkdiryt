const express = require('express');
const ytdl = require('ytdl-core');
const YouTubeSearch = require('youtube-search-python');
const path = require('path');
const fs = require('fs');
const { URL } = require('url');

const app = express();
app.use(express.json());

const YOUTUBE_REGEX = /(?:youtube\.com|youtu\.be)/;

const timeToSeconds = (duration) => {
    const [h = '0', m = '0', s = '0'] = duration.match(/\d+/g) || [];
    return (+h * 3600) + (+m * 60) + (+s);
};

const isValidYouTubeURL = (url) => YOUTUBE_REGEX.test(url);

// Fetch video details
app.post('/fetch', async (req, res) => {
    const { url } = req.body;
    if (!url || !isValidYouTubeURL(url)) {
        return res.status(400).json({ error: 'Invalid or missing URL' });
    }

    try {
        const searchResult = await YouTubeSearch.search(url, 1);
        const video = searchResult[0];
        const durationSec = timeToSeconds(video.duration);
        res.json({
            title: video.title,
            duration: video.duration,
            duration_sec: durationSec,
            thumbnail: video.thumbnails[0],
            video_id: video.id
        });
    } catch (error) {
        res.status(500).json({ error: 'Error fetching video details' });
    }
});

// Download video/audio
app.post('/download', async (req, res) => {
    const { url, format_id, title, songaudio, songvideo, video } = req.body;
    if (!url || !isValidYouTubeURL(url)) {
        return res.status(400).json({ error: 'Invalid or missing URL' });
    }

    try {
        const info = await ytdl.getInfo(url);
        const format = ytdl.chooseFormat(info.formats, { quality: format_id }) || info.formats[0];
        const outputFilePath = path.resolve(__dirname, 'downloads', `${title || info.videoDetails.title}.${format.container}`);

        if (!fs.existsSync(path.dirname(outputFilePath))) {
            fs.mkdirSync(path.dirname(outputFilePath), { recursive: true });
        }

        ytdl(url, { format }).pipe(fs.createWriteStream(outputFilePath));

        res.json({ file_path: outputFilePath });
    } catch (error) {
        res.status(500).json({ error: 'Error downloading video/audio' });
    }
});

// Create additional routes if needed

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
