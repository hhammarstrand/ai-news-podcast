# Podcast Distribution Guide

## Overview

This guide covers how to set up podcast distribution for Spotify for Podcasters and Apple Podcasts Connect after the RSS feed is live.

## Prerequisites

- RSS feed hosted at a public URL (e.g., `https://your-bucket.s3.amazonaws.com/feed.xml`)
- Accounts on Spotify for Podcasters and Apple Podcasts Connect

## RSS Feed URL

After deploying the infrastructure, the RSS feed will be available at:
```
https://{s3_bucket_name}.s3.eu-north-1.amazonaws.com/feed.xml
```

The S3 bucket name is output by Terraform as `s3_bucket_name`.

## Spotify for Podcasters

### Steps to Submit:

1. **Create Spotify for Podcasters account**
   - Go to [Spotify for Podcasters](https://podcasters.spotify.com/)
   - Sign up with your Google account or email

2. **Add your podcast**
   - Click "Add a podcast"
   - Select "RSS Feed"
   - Enter your RSS feed URL
   - Spotify will verify the feed automatically

3. **Submit for review**
   - Once verified, your podcast will appear in the dashboard
   - Review and publish your episodes

### Notes:
- Spotify automatically pulls new episodes from the RSS feed
- Allow 24-48 hours for new episodes to appear after publishing
- Make sure the RSS feed is publicly accessible before submitting

## Apple Podcasts Connect

### Steps to Submit:

1. **Create Apple Podcasts Connect account**
   - Go to [Apple Podcasts Connect](https://podcastsconnect.apple.com/)
   - Sign in with your Apple ID
   - Complete the publisher verification if prompted

2. **Add your podcast**
   - Click the "+" button
   - Select "Add a show"
   - Choose "Add using RSS feed"
   - Enter your RSS feed URL

3. **Review and publish**
   - Apple will review your podcast (can take 24-48 hours)
   - Once approved, your podcast will be live on Apple Podcasts

### Notes:
- Apple requires a unique RSS feed for each podcast
- Make sure all required tags are in the RSS feed (title, description, itunes:author, itunes:image, etc.)
- Episodes typically appear within 24 hours of approval

## RSS Feed Requirements

The pipeline generates an RSS 2.0 feed with iTunes namespace extensions. Required elements:

```xml
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>AI Nyhetspodcast</title>
    <language>sv</language>
    <itunes:author>AI News AB</itunes:author>
    <itunes:image href="https://your-bucket.s3.amazonaws.com/artwork.jpg"/>
    <item>
      <title>Episode Title</title>
      <description>Episode description</description>
      <enclosure url="https://your-bucket.s3.amazonaws.com/episodes/episode.mp3" 
                 length="1234567" type="audio/mpeg"/>
      <guid>unique-episode-guid</guid>
      <pubDate>Thu, 01 Jan 2025 06:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
```

## Verifying the RSS Feed

After deployment, verify the RSS feed is working:

```bash
# Check if feed is accessible
curl -I https://your-bucket.s3.amazonaws.com/feed.xml

# Validate RSS structure
curl -s https://your-bucket.s3.amazonaws.com/feed.xml | head -50
```

## Episode Numbering

Episodes are numbered sequentially by date. The most recent episode is at the top of the feed.

## Troubleshooting

### Spotify not finding new episodes
- Verify the RSS feed URL is correct
- Check that the S3 bucket policy allows public read
- Ensure episode `enclosure` URLs are publicly accessible

### Apple Podcasts showing old episodes
- Apple caches episode data; allow 24-48 hours for updates
- Verify the pubDate in the RSS feed is correct

### Audio files not playing
- Check that the `enclosure` length and type are correct
- Verify the MP3 files are properly uploaded to S3

## Automatic Updates

Once set up, new episodes will be automatically added to both platforms when:
1. The pipeline runs successfully
2. New episodes are uploaded to S3
3. The RSS feed is updated with new episode entries

The pipeline handles this automatically - no manual intervention needed for each episode.