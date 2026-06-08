"""
REEL-MAKER — Viral Short-Form Video Engine & Social Auto-Publisher
====================================================================
Algorithm-optimized reels for Instagram, TikTok, YouTube Shorts, and Facebook.
Composes vertical 9:16 video with hooks, captions, voiceover, and auto-posting.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog
from PIL import Image, ImageDraw, ImageFont

log = structlog.get_logger("brainiac.reel_maker")

OUTPUT_DIR = Path(os.getenv("BRAINIAC_REEL_OUTPUT_DIR", "/tmp/brainiac-reels"))


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"


class ReelStyle(str, Enum):
    VIRAL_HOOK = "viral_hook"
    STORYTELLING = "storytelling"
    TUTORIAL = "tutorial"
    MOTIVATIONAL = "motivational"
    PRODUCT = "product"
    TREND_REMIX = "trend_remix"
    NEWS_BUZZ = "news_buzz"


class HookType(str, Enum):
    CURIOSITY_GAP = "curiosity_gap"
    SHOCK_STAT = "shock_stat"
    POV = "pov"
    BEFORE_AFTER = "before_after"
    LISTICLE = "listicle"
    CONTROVERSY = "controversy"
    QUESTION = "question"


class JobStatus(str, Enum):
    QUEUED = "queued"
    SCRIPTING = "scripting"
    RENDERING = "rendering"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass(frozen=True)
class PlatformSpec:
    platform: Platform
    aspect_ratio: str
    width: int
    height: int
    min_duration_s: float
    max_duration_s: float
    optimal_duration_s: float
    hook_window_s: float
    caption_required: bool
    max_hashtags: int
    algorithm_tips: list[str]


PLATFORM_SPECS: dict[Platform, PlatformSpec] = {
    Platform.TIKTOK: PlatformSpec(
        platform=Platform.TIKTOK,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration_s=7.0,
        max_duration_s=60.0,
        optimal_duration_s=21.0,
        hook_window_s=3.0,
        caption_required=True,
        max_hashtags=5,
        algorithm_tips=[
            "Hook in first 1-3 seconds — retention drops sharply after 3s",
            "Use trending sounds; audio drives FYP distribution",
            "Burn captions; 80%+ watch muted",
            "Loop-friendly ending boosts rewatch rate",
            "Post 1-3x daily at peak audience hours",
            "Reply to comments in first hour to boost engagement velocity",
        ],
    ),
    Platform.INSTAGRAM: PlatformSpec(
        platform=Platform.INSTAGRAM,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration_s=5.0,
        max_duration_s=90.0,
        optimal_duration_s=30.0,
        hook_window_s=2.0,
        caption_required=True,
        max_hashtags=8,
        algorithm_tips=[
            "First frame must stop the scroll — bold text + motion",
            "Trending audio within 24-48h of peak usage",
            "Share to Stories within 30 min to seed Explore",
            "Saves and shares weigh more than likes for reach",
            "Use 3-5 niche + 2-3 broad hashtags",
            "CTA in last 3 seconds (follow, save, share)",
        ],
    ),
    Platform.YOUTUBE: PlatformSpec(
        platform=Platform.YOUTUBE,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration_s=5.0,
        max_duration_s=60.0,
        optimal_duration_s=45.0,
        hook_window_s=3.0,
        caption_required=True,
        max_hashtags=3,
        algorithm_tips=[
            "Title must include #Shorts for Shorts shelf",
            "Hook + payoff in under 60s; loop ending helps",
            "High CTR thumbnail frame at 0:00",
            "Pinned comment with CTA drives subs",
            "Post when subscribers are online (Analytics)",
        ],
    ),
    Platform.FACEBOOK: PlatformSpec(
        platform=Platform.FACEBOOK,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        min_duration_s=5.0,
        max_duration_s=90.0,
        optimal_duration_s=30.0,
        hook_window_s=2.5,
        caption_required=True,
        max_hashtags=5,
        algorithm_tips=[
            "Reels tab favors native uploads over cross-posts",
            "Emotional hooks outperform informational in feed",
            "Share to Groups for initial velocity",
            "Text overlays increase completion on mute",
            "Post Reels + feed video for dual distribution",
        ],
    ),
}


TRENDING_HOOKS: dict[HookType, list[str]] = {
    HookType.CURIOSITY_GAP: [
        "Nobody talks about this…",
        "Wait until you see #3",
        "This changed everything for me",
        "You're doing {topic} wrong",
    ],
    HookType.SHOCK_STAT: [
        "97% of people don't know this",
        "I made $X in 30 days doing this",
        "{topic} in 60 seconds",
    ],
    HookType.POV: [
        "POV: you finally figured out {topic}",
        "POV: it's 3am and you discover this",
    ],
    HookType.BEFORE_AFTER: [
        "Before vs After {topic}",
        "Day 1 vs Day 30",
    ],
    HookType.LISTICLE: [
        "3 hacks that actually work",
        "5 mistakes killing your {topic}",
        "Top 3 trends right now",
    ],
    HookType.CONTROVERSY: [
        "Unpopular opinion: {topic}",
        "Stop doing this immediately",
    ],
    HookType.QUESTION: [
        "Did you know this about {topic}?",
        "Why is nobody talking about {topic}?",
    ],
}


TRENDING_HASHTAGS: dict[str, list[str]] = {
    "general": ["#fyp", "#foryou", "#viral", "#trending", "#reels"],
    "instagram": ["#reelsinstagram", "#explorepage", "#instareels"],
    "tiktok": ["#fyp", "#foryoupage", "#tiktokviral"],
    "youtube": ["#shorts", "#youtubeshorts"],
    "facebook": ["#reels", "#facebookreels"],
}


@dataclass
class ReelScript:
    hook: str
    body_lines: list[str]
    cta: str
    hook_type: HookType
    duration_s: float
    caption: str
    hashtags: list[str]
    title: str
    on_screen_text: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "hook": self.hook,
            "body_lines": self.body_lines,
            "cta": self.cta,
            "hook_type": self.hook_type.value,
            "duration_s": self.duration_s,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "title": self.title,
            "on_screen_text": self.on_screen_text,
        }


@dataclass
class ReelJob:
    job_id: str
    topic: str
    style: ReelStyle
    platforms: list[Platform]
    status: JobStatus
    script: ReelScript | None = None
    video_path: str | None = None
    thumbnail_path: str | None = None
    audio_path: str | None = None
    publish_results: dict[str, Any] = field(default_factory=dict)
    algorithm_score: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    error: str | None = None
    progress_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "topic": self.topic,
            "style": self.style.value,
            "platforms": [p.value for p in self.platforms],
            "status": self.status.value,
            "script": {
                "hook": self.script.hook,
                "body_lines": self.script.body_lines,
                "cta": self.script.cta,
                "hook_type": self.script.hook_type.value,
                "duration_s": self.script.duration_s,
                "caption": self.script.caption,
                "hashtags": self.script.hashtags,
                "title": self.script.title,
                "on_screen_text": self.script.on_screen_text,
            }
            if self.script
            else None,
            "video_path": self.video_path,
            "thumbnail_path": self.thumbnail_path,
            "audio_path": self.audio_path,
            "publish_results": self.publish_results,
            "algorithm_score": self.algorithm_score,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "progress_pct": self.progress_pct,
        }


class ReelMaker:
    """
    REEL-MAKER — viral short-form video pipeline + social auto-publisher.

    Pipeline: brief → algorithm-tuned script → vertical render → optional TTS → publish.
    Integrates CreativeEngine (visuals), SonicMatrix (voiceover), NexusSync (webhook dispatch).
    """

    def __init__(
        self,
        *,
        sonic: Any | None = None,
        creative: Any | None = None,
        nexus: Any | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._sonic = sonic
        self._creative = creative
        self._nexus = nexus
        self._output_dir = output_dir or OUTPUT_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, ReelJob] = {}
        self._completed_count = 0
        self._publish_count = 0
        log.info("reel_maker.init", output_dir=str(self._output_dir))

    def set_dependencies(
        self, *, sonic: Any = None, creative: Any = None, nexus: Any = None
    ) -> None:
        if sonic is not None:
            self._sonic = sonic
        if creative is not None:
            self._creative = creative
        if nexus is not None:
            self._nexus = nexus

    # ── Public API ────────────────────────────────────────────────────────────

    def list_platform_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "platform": spec.platform.value,
                "aspect_ratio": spec.aspect_ratio,
                "resolution": f"{spec.width}x{spec.height}",
                "duration_range_s": [spec.min_duration_s, spec.max_duration_s],
                "optimal_duration_s": spec.optimal_duration_s,
                "hook_window_s": spec.hook_window_s,
                "algorithm_tips": spec.algorithm_tips,
            }
            for spec in PLATFORM_SPECS.values()
        ]

    def get_trends(self, niche: str = "general") -> dict[str, Any]:
        niche_key = niche.lower().replace(" ", "_")
        hooks = []
        for hook_type, templates in TRENDING_HOOKS.items():
            for tmpl in templates[:2]:
                hooks.append(
                    {
                        "type": hook_type.value,
                        "template": tmpl.replace("{topic}", niche or "your niche"),
                    }
                )
        hashtags = TRENDING_HASHTAGS.get("general", []) + TRENDING_HASHTAGS.get(niche_key, [])
        return {
            "niche": niche,
            "viral_hooks": hooks[:12],
            "trending_hashtags": list(dict.fromkeys(hashtags))[:15],
            "optimal_post_times_utc": ["14:00", "17:00", "21:00"],
            "content_styles": [s.value for s in ReelStyle],
            "retention_tactics": [
                "Pattern interrupt every 3-5 seconds",
                "Text pop on beat drops",
                "Open loop in hook, close in CTA",
                "Fast cuts (0.8-1.5s per scene)",
            ],
        }

    async def compose(
        self,
        topic: str,
        *,
        style: ReelStyle = ReelStyle.VIRAL_HOOK,
        platforms: list[Platform] | None = None,
        duration_s: float | None = None,
        hook_type: HookType | None = None,
        niche_hashtags: list[str] | None = None,
        voiceover: bool = True,
    ) -> ReelJob:
        platforms = platforms or [Platform.TIKTOK, Platform.INSTAGRAM]
        job_id = uuid.uuid4().hex[:12]
        job = ReelJob(
            job_id=job_id,
            topic=topic,
            style=style,
            platforms=platforms,
            status=JobStatus.QUEUED,
        )
        self._jobs[job_id] = job

        try:
            job.status = JobStatus.SCRIPTING
            job.progress_pct = 10.0
            primary = platforms[0]
            spec = PLATFORM_SPECS[primary]
            target_duration = duration_s or spec.optimal_duration_s
            target_duration = max(spec.min_duration_s, min(spec.max_duration_s, target_duration))

            script = self._generate_script(
                topic, style, primary, target_duration, hook_type, niche_hashtags
            )
            job.script = script
            job.algorithm_score = self._score_script(script, platforms)
            job.progress_pct = 35.0

            job.status = JobStatus.RENDERING
            video_path, thumb_path, audio_path = self._render_video(
                job_id, script, spec, style=style
            )
            h264_path = self._transcode_h264(video_path)
            if h264_path is not None:
                video_path = h264_path
            job.video_path = str(video_path)
            job.thumbnail_path = str(thumb_path)
            job.progress_pct = 80.0

            if voiceover and self._sonic is not None:
                audio_path = self._synthesize_voiceover(job_id, script)
                if audio_path:
                    job.audio_path = str(audio_path)
                    muxed = self._mux_audio_video(video_path, audio_path)
                    if muxed:
                        job.video_path = str(muxed)

            job.status = JobStatus.READY
            job.progress_pct = 100.0
            job.completed_at = time.time()
            self._completed_count += 1
            log.info("reel_maker.compose_done", job_id=job_id, score=job.algorithm_score)
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            log.error("reel_maker.compose_failed", job_id=job_id, error=str(exc))
        return job

    def get_job(self, job_id: str) -> ReelJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[ReelJob]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def publish(
        self,
        job_id: str,
        platforms: list[Platform] | None = None,
        *,
        schedule_at: float | None = None,
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        if job.status not in (JobStatus.READY, JobStatus.PUBLISHED):
            raise ValueError(f"Job not ready for publish: {job.status.value}")
        if not job.video_path or not Path(job.video_path).exists():
            raise ValueError("Video file missing")

        targets = platforms or job.platforms
        job.status = JobStatus.PUBLISHING
        use_dry_run = dry_run if dry_run is not None else not self._any_platform_configured()

        results: dict[str, Any] = {}
        for platform in targets:
            adapter = self._publisher_for(platform)
            payload = self._build_publish_payload(job, platform)
            if schedule_at:
                payload["scheduled_at"] = schedule_at
            result = await adapter(payload, dry_run=use_dry_run)
            results[platform.value] = result

            if self._nexus is not None and not use_dry_run:
                with contextlib.suppress(Exception):
                    await self._nexus.publish(
                        f"social-{platform.value}",
                        f"reels/{job_id}",
                        {"platform": platform.value, "result": result},
                    )

        job.publish_results = results
        job.status = JobStatus.PUBLISHED
        self._publish_count += 1
        return {"job_id": job_id, "platforms": results, "dry_run": use_dry_run}

    # ── Script generation ─────────────────────────────────────────────────────

    def _generate_script(
        self,
        topic: str,
        style: ReelStyle,
        platform: Platform,
        duration_s: float,
        hook_type: HookType | None,
        niche_hashtags: list[str] | None,
    ) -> ReelScript:
        hook_type = hook_type or self._pick_hook_type(style)
        templates = TRENDING_HOOKS[hook_type]
        hook = templates[hash(topic) % len(templates)].replace("{topic}", topic)

        body_templates: dict[ReelStyle, list[str]] = {
            ReelStyle.VIRAL_HOOK: [
                f"Here's the truth about {topic}",
                "Most people skip this step",
                "But this one trick changes the game",
            ],
            ReelStyle.TUTORIAL: [
                f"Step 1: Start with {topic}",
                "Step 2: Apply this daily",
                "Step 3: Watch results in 7 days",
            ],
            ReelStyle.MOTIVATIONAL: [
                "You don't need permission",
                f"Master {topic} one day at a time",
                "Your future self will thank you",
            ],
            ReelStyle.PRODUCT: [
                f"This solves {topic} instantly",
                "Thousands already switched",
                "Link in bio — limited offer",
            ],
            ReelStyle.STORYTELLING: [
                f"I almost gave up on {topic}",
                "Then I discovered this",
                "Now everything's different",
            ],
            ReelStyle.TREND_REMIX: [
                f"Everyone's doing {topic} wrong",
                "Here's the trend done right",
                "Save this before it's gone",
            ],
            ReelStyle.NEWS_BUZZ: [
                f"Breaking: {topic} just changed",
                "Here's what it means for you",
                "Share before everyone knows",
            ],
        }
        body = body_templates.get(style, body_templates[ReelStyle.VIRAL_HOOK])
        cta = "Follow for more 🔥" if platform != Platform.YOUTUBE else "Subscribe for daily Shorts"

        spec = PLATFORM_SPECS[platform]
        tags = list(TRENDING_HASHTAGS.get("general", []))
        tags.extend(TRENDING_HASHTAGS.get(platform.value, []))
        if niche_hashtags:
            tags.extend(niche_hashtags)
        tags = list(dict.fromkeys(tags))[: spec.max_hashtags]
        niche_tag = f"#{topic.replace(' ', '').lower()[:20]}"
        if niche_tag not in tags:
            tags.insert(0, niche_tag)

        on_screen = [hook, *body[:2], cta]
        caption = f"{hook}\n\n" + "\n".join(body) + f"\n\n{cta}\n" + " ".join(tags)
        title = f"{hook} | {topic}"
        if platform == Platform.YOUTUBE and "#Shorts" not in title:
            title = f"{title} #Shorts"

        return ReelScript(
            hook=hook,
            body_lines=body,
            cta=cta,
            hook_type=hook_type,
            duration_s=duration_s,
            caption=caption,
            hashtags=tags,
            title=title,
            on_screen_text=on_screen,
        )

    @staticmethod
    def _pick_hook_type(style: ReelStyle) -> HookType:
        mapping = {
            ReelStyle.VIRAL_HOOK: HookType.CURIOSITY_GAP,
            ReelStyle.TUTORIAL: HookType.LISTICLE,
            ReelStyle.MOTIVATIONAL: HookType.POV,
            ReelStyle.PRODUCT: HookType.BEFORE_AFTER,
            ReelStyle.STORYTELLING: HookType.QUESTION,
            ReelStyle.TREND_REMIX: HookType.CONTROVERSY,
            ReelStyle.NEWS_BUZZ: HookType.SHOCK_STAT,
        }
        return mapping.get(style, HookType.CURIOSITY_GAP)

    def _score_script(self, script: ReelScript, platforms: list[Platform]) -> float:
        score = 50.0
        if len(script.hook) <= 60:
            score += 10.0
        if script.hook_type in (HookType.CURIOSITY_GAP, HookType.SHOCK_STAT):
            score += 8.0
        if 15.0 <= script.duration_s <= 45.0:
            score += 10.0
        if len(script.hashtags) >= 3:
            score += 5.0
        if len(script.on_screen_text) >= 3:
            score += 7.0
        for p in platforms:
            spec = PLATFORM_SPECS[p]
            if spec.min_duration_s <= script.duration_s <= spec.max_duration_s:
                score += 5.0
        return min(100.0, round(score, 1))

    # ── Video rendering ───────────────────────────────────────────────────────

    def _visual_palettes(
        self, style: ReelStyle
    ) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
        palettes: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
            ((138, 43, 226), (255, 0, 128)),
            ((0, 191, 255), (0, 255, 200)),
            ((255, 94, 0), (255, 0, 110)),
            ((46, 204, 113), (52, 152, 219)),
            ((255, 195, 0), (255, 87, 34)),
            ((63, 81, 181), (156, 39, 176)),
        ]
        if self._creative is None:
            return palettes

        from brainiac.core.creative_engine import Style as CreativeStyle

        style_map = {
            ReelStyle.VIRAL_HOOK: CreativeStyle.CINEMATIC,
            ReelStyle.TUTORIAL: CreativeStyle.TECHNICAL,
            ReelStyle.MOTIVATIONAL: CreativeStyle.ILLUSTRATION,
            ReelStyle.PRODUCT: CreativeStyle.PHOTOREALISTIC,
            ReelStyle.STORYTELLING: CreativeStyle.CINEMATIC,
            ReelStyle.TREND_REMIX: CreativeStyle.ABSTRACT,
            ReelStyle.NEWS_BUZZ: CreativeStyle.TECHNICAL,
        }
        ce_style = style_map.get(style, CreativeStyle.ABSTRACT)
        spec = self._creative.generate_image_prompt("vertical reel background", style=ce_style)
        offset = hash(spec["style"]) % len(palettes)
        return palettes[offset:] + palettes[:offset]

    def _render_video(
        self,
        job_id: str,
        script: ReelScript,
        spec: PlatformSpec,
        *,
        style: ReelStyle = ReelStyle.VIRAL_HOOK,
    ) -> tuple[Path, Path, Path | None]:
        w, h = spec.width, spec.height
        fps = 30
        total_frames = int(script.duration_s * fps)
        scenes = script.on_screen_text
        frames_per_scene = max(1, total_frames // len(scenes))

        video_path = self._output_dir / f"{job_id}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

        palettes = self._visual_palettes(style)

        for frame_idx in range(total_frames):
            scene_idx = min(frame_idx // frames_per_scene, len(scenes) - 1)
            text = scenes[scene_idx]
            c1, c2 = palettes[scene_idx % len(palettes)]
            t = frame_idx / max(1, total_frames - 1)
            pulse = 0.5 + 0.5 * np.sin(frame_idx * 0.15)
            img = self._gradient_frame(w, h, c1, c2, t, pulse)
            img = self._draw_text_overlay(img, text, w, h, bold=(scene_idx == 0))
            if scene_idx == 0:
                img = self._draw_hook_badge(img, "HOOK", w)
            writer.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))

        writer.release()

        thumb_path = self._output_dir / f"{job_id}_thumb.jpg"
        thumb = self._gradient_frame(w, h, (138, 43, 226), (255, 0, 128), 0.0, 1.0)
        thumb = self._draw_text_overlay(thumb, script.hook, w, h, bold=True)
        thumb.save(thumb_path, quality=92)

        return video_path, thumb_path, None

    def _transcode_h264(self, video_path: Path) -> Path | None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg or not video_path.is_file():
            return None
        out_path = self._output_dir / f"{video_path.stem}_h264.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            log.warning("reel_maker.transcode_failed", error=str(exc))
            return None
        if not out_path.is_file():
            return None
        with contextlib.suppress(OSError):
            video_path.unlink()
        return out_path

    @staticmethod
    def _gradient_frame(
        w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int], t: float, pulse: float
    ) -> Image.Image:
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            blend = (y / h) * 0.7 + t * 0.3
            for ch in range(3):
                arr[y, :, ch] = int(c1[ch] * (1 - blend) + c2[ch] * blend * pulse)
        return Image.fromarray(arr)

    @staticmethod
    def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for path in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ):
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def _draw_text_overlay(
        self, img: Image.Image, text: str, w: int, h: int, *, bold: bool = False
    ) -> Image.Image:
        draw = ImageDraw.Draw(img)
        font_size = 72 if bold else 56
        font = self._get_font(font_size)
        words = text.split()
        lines: list[str] = []
        current = ""
        max_width = int(w * 0.85)
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if not lines:
            lines = [text[:40]]

        line_height = font_size + 16
        total_h = len(lines) * line_height
        y_start = (h - total_h) // 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (w - tw) // 2
            y = y_start + i * line_height
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
        return img

    @staticmethod
    def _draw_hook_badge(img: Image.Image, label: str, w: int) -> Image.Image:
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((40, 80, 200, 140), radius=12, fill=(255, 0, 110))
        draw.text((60, 95), label, fill=(255, 255, 255))
        return img

    def _synthesize_voiceover(self, job_id: str, script: ReelScript) -> Path | None:
        if self._sonic is None:
            return None
        narration = f"{script.hook}. {' '.join(script.body_lines)}. {script.cta}"
        try:
            result = self._sonic.synthesize(narration[:500])
            if not result.audio_bytes:
                return None
            audio_path = self._output_dir / f"{job_id}.mp3"
            audio_path.write_bytes(result.audio_bytes)
            return audio_path
        except Exception as exc:
            log.warning("reel_maker.tts_failed", error=str(exc))
            return None

    def _mux_audio_video(self, video_path: Path, audio_path: Path) -> Path | None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None
        out_path = self._output_dir / f"{video_path.stem}_muxed.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            return out_path
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            log.warning("reel_maker.mux_failed", error=str(exc))
            return None

    # ── Social publishing ─────────────────────────────────────────────────────

    def _any_platform_configured(self) -> bool:
        keys = (
            "INSTAGRAM_ACCESS_TOKEN",
            "TIKTOK_ACCESS_TOKEN",
            "YOUTUBE_ACCESS_TOKEN",
            "FACEBOOK_ACCESS_TOKEN",
        )
        return any(os.getenv(k) for k in keys)

    def _publisher_for(self, platform: Platform) -> Callable[..., Any]:
        return {
            Platform.INSTAGRAM: self._publish_instagram,
            Platform.TIKTOK: self._publish_tiktok,
            Platform.YOUTUBE: self._publish_youtube,
            Platform.FACEBOOK: self._publish_facebook,
        }[platform]

    def _build_publish_payload(self, job: ReelJob, platform: Platform) -> dict[str, Any]:
        assert job.script is not None
        return {
            "video_path": job.video_path,
            "caption": job.script.caption,
            "title": job.script.title,
            "hashtags": job.script.hashtags,
            "thumbnail_path": job.thumbnail_path,
            "job_id": job.job_id,
            "platform": platform.value,
        }

    async def _publish_instagram(self, payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        user_id = os.getenv("INSTAGRAM_USER_ID")
        if dry_run or not token or not user_id:
            return self._dry_run_result(Platform.INSTAGRAM, payload)
        return await self._http_publish(
            f"https://graph.facebook.com/v19.0/{user_id}/media",
            {
                "access_token": token,
                "media_type": "REELS",
                "video_url": payload.get("video_url", ""),
                "caption": payload["caption"][:2200],
            },
            Platform.INSTAGRAM,
        )

    async def _publish_tiktok(self, payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        token = os.getenv("TIKTOK_ACCESS_TOKEN")
        if dry_run or not token:
            return self._dry_run_result(Platform.TIKTOK, payload)
        return await self._http_publish(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            {
                "post_info": {
                    "title": payload["caption"][:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                },
            },
            Platform.TIKTOK,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def _publish_youtube(self, payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        token = os.getenv("YOUTUBE_ACCESS_TOKEN")
        if dry_run or not token:
            return self._dry_run_result(Platform.YOUTUBE, payload)
        return {
            "platform": Platform.YOUTUBE.value,
            "status": "queued",
            "message": "Upload via YouTube Data API resumable upload — configure OAuth refresh token",
            "title": payload["title"],
        }

    async def _publish_facebook(self, payload: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        token = os.getenv("FACEBOOK_ACCESS_TOKEN")
        page_id = os.getenv("FACEBOOK_PAGE_ID")
        if dry_run or not token or not page_id:
            return self._dry_run_result(Platform.FACEBOOK, payload)
        return await self._http_publish(
            f"https://graph.facebook.com/v19.0/{page_id}/video_reels",
            {"access_token": token, "description": payload["caption"][:2200]},
            Platform.FACEBOOK,
        )

    @staticmethod
    def _dry_run_result(platform: Platform, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "platform": platform.value,
            "status": "dry_run",
            "message": (
                f"Simulated publish — set {platform.value.upper()}_ACCESS_TOKEN to go live"
            ),
            "preview": {
                "title": payload.get("title"),
                "caption_preview": (payload.get("caption") or "")[:120] + "…",
                "video_path": payload.get("video_path"),
            },
            "estimated_reach": "high" if len(payload.get("hashtags", [])) >= 3 else "medium",
        }

    @staticmethod
    async def _http_publish(
        url: str,
        data: dict[str, Any],
        platform: Platform,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=data, headers=headers or {})
                body = resp.json() if resp.content else {}
                return {
                    "platform": platform.value,
                    "status": "submitted" if resp.is_success else "error",
                    "http_status": resp.status_code,
                    "response": body,
                }
        except Exception as exc:
            return {"platform": platform.value, "status": "error", "error": str(exc)}

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "jobs_total": len(self._jobs),
            "jobs_completed": self._completed_count,
            "jobs_published": self._publish_count,
            "output_dir": str(self._output_dir),
            "platforms_supported": [p.value for p in Platform],
            "social_configured": self._any_platform_configured(),
            "ffmpeg_available": shutil.which("ffmpeg") is not None,
        }
