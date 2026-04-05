"""EpisodePublisher — uploads episode to S3 and updates RSS feed."""

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import boto3

from ..config import settings
from ..editorial.models import PodcastScript

logger = logging.getLogger(__name__)

RSS_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class EpisodePublisher:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        self.bucket = settings.aws_s3_bucket

    def publish(self, episode_path: Path, script: PodcastScript, pub_date: datetime | None = None) -> str:
        """Upload episode MP3 and update RSS feed. Returns the public episode URL."""
        if pub_date is None:
            pub_date = datetime.now(tz=timezone.utc)

        episode_key = f"episodes/{pub_date.strftime('%Y%m%d_%H%M%S')}.mp3"
        episode_url = self._upload_audio(episode_path, episode_key)

        self._update_rss(script, episode_url, episode_path, pub_date)
        logger.info("Episode published: %s", episode_url)
        return episode_url

    def _upload_audio(self, path: Path, key: str) -> str:
        logger.info("Uploading %s → s3://%s/%s", path.name, self.bucket, key)
        self.s3.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": "audio/mpeg", "ACL": "public-read"},
        )
        return f"https://{self.bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"

    def _update_rss(
        self,
        script: PodcastScript,
        episode_url: str,
        episode_path: Path,
        pub_date: datetime,
    ) -> None:
        # Fetch existing feed or create new
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=settings.podcast_rss_s3_key)
            feed_xml = resp["Body"].read()
            root = ET.fromstring(feed_xml)
            channel = root.find("channel")
        except self.s3.exceptions.NoSuchKey:
            root, channel = self._create_feed_skeleton()

        # Add new <item>
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = script.episode_title
        ET.SubElement(item, "description").text = script.episode_summary
        ET.SubElement(item, "pubDate").text = pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        file_size = episode_path.stat().st_size
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", episode_url)
        enclosure.set("length", str(file_size))
        enclosure.set("type", "audio/mpeg")
        guid = ET.SubElement(item, "guid")
        guid.text = episode_url

        feed_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True).encode()
        self.s3.put_object(
            Bucket=self.bucket,
            Key=settings.podcast_rss_s3_key,
            Body=feed_bytes,
            ContentType="application/rss+xml",
            ACL="public-read",
        )
        logger.info("RSS feed updated")

    def _create_feed_skeleton(self) -> tuple[ET.Element, ET.Element]:
        root = ET.Element("rss", version="2.0")
        root.set("xmlns:itunes", RSS_NAMESPACE)
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = settings.podcast_title
        ET.SubElement(channel, "language").text = settings.podcast_language
        ET.SubElement(channel, "itunes:author").text = settings.podcast_author
        return root, channel
