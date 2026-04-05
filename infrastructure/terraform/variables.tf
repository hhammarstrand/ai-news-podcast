variable "anthropic_api_key" {
  description = "Anthropic API key for Claude"
  type        = string
  sensitive   = true
}

variable "elevenlabs_api_key" {
  description = "ElevenLabs API key for TTS"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "PostgreSQL database connection string"
  type        = string
  sensitive   = true
}

variable "news_api_key" {
  description = "NewsAPI.org API key"
  type        = string
  sensitive   = true
}