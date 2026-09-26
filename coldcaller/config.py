"""Validated campaign and environment configuration."""
import os
from datetime import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: time = time(9)
    end: time = time(20)

    @model_validator(mode="after")
    def ordered(self):
        if self.start.tzinfo or self.end.tzinfo:
            raise ValueError("calling window times must be local, without timezone offsets")
        if self.start >= self.end:
            raise ValueError("calling window must start before end; overnight windows are unsupported")
        return self


class Campaign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_name: str = "Alex"
    company: str = "Example Workshop"
    offer: str = "A workflow planning meeting"
    qualification_questions: list[str] = Field(default_factory=lambda: ["What would you like to automate?"])
    objection_notes: list[str] = Field(default_factory=list)
    voice: str = "marin"
    calling_window: Window = Field(default_factory=Window)
    require_consent: bool = True
    max_attempts_per_lead: int = Field(default=2, ge=1)
    seconds_between_calls: float = Field(default=5, ge=0)
    max_concurrent_calls: int = Field(default=1, ge=1)
    booking_webhook_url: HttpUrl | None = None
    ai_disclosure: bool = True
    ai_disclosure_line: str = "Hello, I am an AI voice assistant calling for Example Workshop."
    voicemail_enabled: bool = False
    voicemail_message: str = "This is an AI voice assistant. Goodbye."
    max_call_seconds: int = Field(default=300, ge=30, le=14400)

    @model_validator(mode="after")
    def disclosure_present(self):
        if self.ai_disclosure and not self.ai_disclosure_line.strip():
            raise ValueError("AI disclosure line is required when disclosure is enabled")
        return self


def load_campaign(path: str | Path) -> Campaign:
    try:
        contents = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid campaign YAML: {exc}") from exc
    return Campaign.model_validate(contents or {})


class Settings(BaseModel):
    account_sid: str = ""
    auth_token: str = ""
    phone_number: str = ""
    openai_key: str = ""
    public_url: str = ""
    data_dir: Path = Path("data")
    dnc_path: Path = Path("dnc.txt")
    validate_signatures: bool = True

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                   auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                   phone_number=os.getenv("TWILIO_PHONE_NUMBER", ""),
                   openai_key=os.getenv("OPENAI_API_KEY", ""),
                   public_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
                   data_dir=Path(os.getenv("DATA_DIR", "data")),
                   dnc_path=Path(os.getenv("DNC_PATH", "dnc.txt")),
                   validate_signatures=os.getenv("VALIDATE_TWILIO_SIGNATURES", "true").lower() != "false")

    def live_errors(self) -> list[str]:
        missing = [name for name in ("account_sid", "auth_token", "phone_number", "openai_key")
                   if not getattr(self, name) or getattr(self, name) == "replace_me"]
        if not self.public_url.startswith("https://"):
            missing.append("public_url (HTTPS required)")
        return missing
