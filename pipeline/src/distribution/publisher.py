"""EpisodePublisher — uploads episode to S3 or saves locally."""

import json
import logging
import shutil
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
        self.use_r2 = bool(settings.r2_endpoint_url and settings.r2_bucket)
        self.use_aws = bool(settings.aws_s3_bucket)
        self.output_dir = Path(settings.pipeline_output_dir) / "published"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.use_r2:
            self.s3 = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
                region_name="auto",
            )
            self.bucket = settings.r2_bucket
            self.public_url = settings.r2_public_url
        elif self.use_aws:
            self.s3 = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id or None,
                aws_secret_access_key=settings.aws_secret_access_key or None,
            )
            self.bucket = settings.aws_s3_bucket
            self.public_url = f"https://{settings.aws_s3_bucket}.s3.{settings.aws_region}.amazonaws.com"
        else:
            self.public_url = None

    def publish(self, episode_path: Path, script: PodcastScript, pub_date: datetime | None = None) -> str:
        """Upload episode MP3 and update RSS feed. Returns the public episode URL."""
        if pub_date is None:
            pub_date = datetime.now(tz=timezone.utc)

        if self.use_aws:
            episode_key = f"episodes/{pub_date.strftime('%Y%m%d_%H%M%S')}.mp3"
            try:
                episode_url = self._upload_audio(episode_path, episode_key)
                self._update_rss(script, episode_url, episode_path, pub_date)
                self._save_script_metadata(script, pub_date)
            except Exception as e:
                logger.warning("S3 upload failed: %s. Falling back to local storage.", e)
                episode_url = self._save_local(episode_path, pub_date)
                self._save_rss_local(script, episode_path, pub_date)
        elif self.use_r2:
            episode_key = f"episodes/{pub_date.strftime('%Y%m%d_%H%M%S')}.mp3"
            try:
                episode_url = self._upload_audio(episode_path, episode_key)
                self._update_rss(script, episode_url, episode_path, pub_date)
                self._save_script_metadata(script, pub_date)
            except Exception as e:
                logger.warning("R2 upload failed: %s. Falling back to local storage.", e)
                episode_url = self._save_local(episode_path, pub_date)
                self._save_rss_local(script, episode_path, pub_date)
        else:
            episode_url = self._save_local(episode_path, pub_date)
            self._save_rss_local(script, episode_path, pub_date)

        logger.info("Episode published: %s", episode_url)
        return episode_url

    def _upload_audio(self, path: Path, key: str) -> str:
        logger.info("Uploading %s → %s/%s", path.name, self.bucket, key)
        self.s3.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )
        return f"{self.public_url}/{key}"

    def _save_local(self, path: Path, pub_date: datetime) -> str:
        filename = f"{pub_date.strftime('%Y%m%d_%H%M%S')}.mp3"
        dest = self.output_dir / filename
        shutil.copy2(path, dest)
        logger.info("Saved episode to %s", dest)
        return str(dest.absolute())

    def _save_script_metadata(self, script: PodcastScript, pub_date: datetime) -> None:
        metadata = {
            "episode_title": script.episode_title,
            "episode_summary": script.episode_summary,
            "pub_date": pub_date.isoformat(),
            "story_urls": script.story_urls,
            "segments": [{"speaker": seg.speaker, "text": seg.text, "story_index": seg.story_index} for seg in script.segments],
        }
        key = f"scripts/{pub_date.strftime('%Y%m%d_%H%M%S')}.json"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(metadata, ensure_ascii=False, indent=2),
            ContentType="application/json",
            ACL="public-read",
        )
        logger.info("Script metadata saved: %s", key)

    def _update_rss(
        self,
        script: PodcastScript,
        episode_url: str,
        episode_path: Path,
        pub_date: datetime,
    ) -> None:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=settings.podcast_rss_s3_key)
            feed_xml = resp["Body"].read()
            root = ET.fromstring(feed_xml)
            channel = root.find("channel")
        except self.s3.exceptions.NoSuchKey:
            root, channel = self._create_feed_skeleton()

        all_children = list(channel)
        existing_items = channel.findall("item")
        metadata_elements = [child for child in all_children if child.tag != "item"]

        item = ET.Element("item")
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

        for child in all_children:
            channel.remove(child)
        for meta in metadata_elements:
            channel.append(meta)
        channel.append(item)
        for old_item in existing_items:
            channel.append(old_item)

        feed_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True).encode()
        self.s3.put_object(
            Bucket=self.bucket,
            Key=settings.podcast_rss_s3_key,
            Body=feed_bytes,
            ContentType="application/rss+xml",
            ACL="public-read",
        )
        logger.info("RSS feed updated")

    def _save_rss_local(
        self,
        script: PodcastScript,
        episode_path: Path,
        pub_date: datetime,
    ) -> None:
        item = {
            "title": script.episode_title,
            "description": script.episode_summary,
            "pub_date": pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "filename": episode_path.name,
            "file_size": episode_path.stat().st_size,
        }
        logger.info("RSS entry saved locally: %s", item)

    def _create_feed_skeleton(self) -> tuple[ET.Element, ET.Element]:
        root = ET.Element("rss", version="2.0")
        root.set("xmlns:itunes", RSS_NAMESPACE)
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = settings.podcast_title
        ET.SubElement(channel, "language").text = settings.podcast_language
        ET.SubElement(channel, "itunes:author").text = settings.podcast_author
        itunes_owner = ET.SubElement(channel, "itunes:owner")
        ET.SubElement(itunes_owner, "itunes:name").text = settings.podcast_author
        ET.SubElement(itunes_owner, "itunes:email").text = settings.podcast_email
        return root, channel
