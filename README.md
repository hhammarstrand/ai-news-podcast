# AI News Podcast Platform

Fully automated AI-generated news podcast covering Swedish news, international news, tech, and AI. Episodes are generated on a schedule — no human journalists required.

## Architecture

```
News Sources → Ingestion → Editorial AI → TTS → Audio Assembly → Distribution
```

### Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend/Pipeline | Python 3.12 | Best ecosystem for AI/ML, LLM SDKs, audio processing |
| Cloud | AWS | Mature, S3 for audio storage, Lambda/ECS for pipeline |
| LLM | MiniMax | Best-in-class for editorial script generation |
| TTS | MiniMax | High-quality Swedish voices via speech-2.8-hd model |
| Audio | ffmpeg | Industry standard for audio mixing/assembly |
| Database | PostgreSQL (RDS) | Episode state, run tracking |
| Queue | AWS SQS | Decoupled pipeline job queuing |
| Storage | AWS S3 | Audio file storage, RSS feed hosting |
| CI/CD | GitHub Actions | Free for public repos, tight GitHub integration |
| Monitoring | AWS CloudWatch | Logs, metrics, alerts |

## Repository Structure

```
.
├── pipeline/               # Python pipeline (core product)
│   ├── src/
│   │   ├── ingestion/      # News fetching from RSS, APIs, scrapers
│   │   ├── editorial/      # MiniMax LLM-powered script generation
│   │   ├── tts/            # MiniMax TTS integration
│   │   ├── audio/          # ffmpeg audio assembly
│   │   ├── distribution/   # RSS feed + podcast platform APIs
│   │   ├── storage/        # S3 operations
│   │   ├── db/             # PostgreSQL models and queries
│   │   └── config.py       # Configuration via environment variables
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── infrastructure/         # AWS infrastructure as code
│   └── terraform/
├── .github/
│   └── workflows/          # CI/CD pipelines
└── docker-compose.yml      # Local development environment
```

## Quick Start

```bash
# Prerequisites: Python 3.12+, Docker, ffmpeg

# 1. Clone and set up
git clone https://github.com/your-org/ai-news-podcast.git
cd ai-news-podcast

# 2. Start local services (PostgreSQL)
docker-compose up -d

# 3. Set up Python environment
cd pipeline
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run the pipeline (generates one episode)
python -m src.main
```

## Environment Variables

See `.env.example` for all required configuration.

Key variables:
- `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID` — MiniMax LLM + TTS credentials
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — AWS credentials
- `AWS_S3_BUCKET` — S3 bucket for audio files
- `DATABASE_URL` — PostgreSQL connection string
- `NEWS_API_KEY` — NewsAPI.org API key

## Episode Generation Flow

1. **Ingestion** — Fetch top stories from RSS feeds (SVT, SR, Reuters, TechCrunch, etc.)
2. **Editorial** — MiniMax LLM selects and ranks stories, writes a podcast script in Swedish/English
3. **TTS** — MiniMax converts script to audio segments per speaker (Swedish_male_1_v1, Swedish_female_1_v1)
4. **Assembly** — ffmpeg mixes segments with intro/outro music into a single MP3
5. **Distribution** — Upload to S3, update RSS feed, push to Spotify/Apple Podcasts
