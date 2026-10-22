from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlsplit
import time
import requests

# Persistent runtime configuration. These values are intentionally not duplicated
# in Python; config/vfx_runtime.json is the canonical source for runtime settings.

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "vfx_runtime.json"

# Unlimited execution is the normal availability mode. Wall-clock deadline
# and progress/stall detection are the real execution boundaries.
DEFAULT_IDENTICAL_ROUND_STALL_THRESHOLD = 2

# Context management policy. This does not remove tools; it only reduces verbose
# schema metadata and bounds the conversational evidence retained by the model.
DEFAULT_CONTEXT_SAFETY_MARGIN_TOKENS = 4096
DEFAULT_RECENT_ROUNDS_TO_KEEP = 2
DEFAULT_TOOL_DESCRIPTION_CHARS = 180
DEFAULT_PROPERTY_DESCRIPTION_CHARS = 72
DEFAULT_TOOL_RESULT_MEMORY_CHARS = 1800
DEFAULT_TOKEN_ESTIMATE_CHARS = 2.0
DEFAULT_CONTEXT_RECOVERY_ATTEMPTS = 2
CONTEXT_TELEMETRY_VERSION = 1

# Model-facing MCP surface policy. Runtime discovery/authorization retains the
# complete registered inventory, but the execution model receives only the two
# distinct capability surfaces: live Resolve compound/default tools plus the
# advanced offline/file/DB tools. The 389 granular --full tools are an alternate
# one-tool-per-API-method representation of the live Resolve API and are therefore
# intentionally not injected alongside the compound surface. Function descriptions
# retain long action catalogs because compound/advanced actions are often encoded
# in prose rather than JSON-Schema enums.
MODEL_COMPOUND_PREFIX = "davinci-resolve_"
MODEL_ADVANCED_PREFIX = "davinci-resolve-advanced_"
MODEL_FUNCTION_DESCRIPTION_CHARS = 20000
MODEL_PROPERTY_DESCRIPTION_CHARS = 160
EXECUTION_MEMORY_MARKER = "EXECUTION MEMORY (runtime-maintained):"
SESSION_CONTEXT_MARKER = "AI DIRECTOR SESSION CONTEXT (runtime-maintained)"
MAX_SESSION_CONTEXT_CHARS = 1048576
MAX_PROGRESS_RESULT_EXCERPT_CHARS = 1600
CONTEXT_OVERFLOW_POLICY_ENV = "FIRSTGAME_VFX_CONTEXT_OVERFLOW_POLICY"
CONTEXT_OVERFLOW_ROLLING = "rolling_window"
CONTEXT_OVERFLOW_STOP = "stop_at_limit"
ROLLING_SESSION_TURN_RE = re.compile(r"(?m)^(?:SESSION TURN|COMPACT SESSION TURN)\s+(\d+)\s*$")
ROLLING_MIN_FULL_RECENT_TURNS = 4

CONFIG_PATH_ENV = "FIRSTGAME_VFX_CONFIG"
BASE_URL_ENV = "FIRSTGAME_VFX_BASE_URL"
MODEL_ENV = "FIRSTGAME_VFX_MODEL"
CONTEXT_ENV = "FIRSTGAME_VFX_CONTEXT_LENGTH"
MAX_OUTPUT_ENV = "FIRSTGAME_VFX_MAX_OUTPUT_TOKENS"
MAX_ROUNDS_ENV = "FIRSTGAME_VFX_MAX_TOOL_ROUNDS"
TIMEOUT_ENV = "FIRSTGAME_VFX_TIMEOUT_SECONDS"
TEMPERATURE_ENV = "FIRSTGAME_VFX_TEMPERATURE"
TOP_P_ENV = "FIRSTGAME_VFX_TOP_P"
TOP_K_ENV = "FIRSTGAME_VFX_TOP_K"
MIN_P_ENV = "FIRSTGAME_VFX_MIN_P"
PRESENCE_PENALTY_ENV = "FIRSTGAME_VFX_PRESENCE_PENALTY"
REPETITION_PENALTY_ENV = "FIRSTGAME_VFX_REPETITION_PENALTY"
CACHE_PROMPT_ENV = "FIRSTGAME_VFX_CACHE_PROMPT"
DIRECTOR_PROMPT_ENV = "FIRSTGAME_VFX_DIRECTOR_PROMPT"
DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "VFXDirector.txt"
)


class VFXRuntimeError(RuntimeError):
    pass


class VFXServerError(VFXRuntimeError):
    pass


class VFXExecutionTimeoutError(VFXRuntimeError):
    pass


class VFXStallError(VFXRuntimeError):
    pass


class VFXContextLimitError(VFXServerError):
    pass


class VFXProtocolError(VFXRuntimeError):
    pass


class VFXAuthorizationError(VFXRuntimeError):
    """Deprecated compatibility alias; MCP owns Resolve operation safety."""
    pass


@dataclass(frozen=True)
class VFXTool:
    name: str
    definition: Mapping[str, Any]
    display_name: str
    description: str
    parameter_names: tuple[str, ...]


@dataclass(frozen=True)
class VFXToolCall:
    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class VFXTurnResult:
    final_message: str
    tool_calls: tuple[VFXToolCall, ...]
    tool_results: tuple[str, ...]
    rounds: int
    telemetry: Mapping[str, Any]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise VFXRuntimeError(f"{name} must be greater than zero.")
    return value


def _env_nonnegative_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be an integer.") from exc
    if value < 0:
        raise VFXRuntimeError(f"{name} must be zero or greater.")
    return value


def _load_runtime_config(path: Path) -> dict[str, Any]:
    """Load the canonical persistent VFX runtime configuration."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VFXRuntimeError(
            f"VFX runtime configuration could not be read: {path}"
        ) from exc
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VFXRuntimeError(
            f"VFX runtime configuration is invalid JSON: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise VFXRuntimeError(
            f"VFX runtime configuration must contain a JSON object: {path}"
        )
    return data


def _config_string(config: Mapping[str, Any], key: str) -> Optional[str]:
    value = config.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise VFXRuntimeError(
            f"VFX runtime configuration field {key!r} must be a non-empty string."
        )
    return value.strip()


def _config_positive_int(config: Mapping[str, Any], key: str) -> Optional[int]:
    value = config.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VFXRuntimeError(
            f"VFX runtime configuration field {key!r} must be a positive integer."
        )
    return value


def _config_nonnegative_int(config: Mapping[str, Any], key: str) -> Optional[int]:
    value = config.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VFXRuntimeError(
            f"VFX runtime configuration field {key!r} must be a non-negative integer."
        )
    return value


def _config_positive_float(config: Mapping[str, Any], key: str) -> Optional[float]:
    value = config.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise VFXRuntimeError(
            f"VFX runtime configuration field {key!r} must be a positive number."
        )
    return float(value)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be a number.") from exc
    if value <= 0:
        raise VFXRuntimeError(f"{name} must be greater than zero.")
    return value


def _env_bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be a number.") from exc
    if value < minimum or value > maximum:
        raise VFXRuntimeError(f"{name} must be from {minimum} through {maximum}.")
    return value


def _env_optional_float(name: str, minimum: float, maximum: float) -> Optional[float]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be a number.") from exc
    if value < minimum or value > maximum:
        raise VFXRuntimeError(f"{name} must be from {minimum} through {maximum}.")
    return value


def _env_optional_int(name: str, minimum: int, maximum: int) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise VFXRuntimeError(f"{name} must be an integer.") from exc
    if value < minimum or value > maximum:
        raise VFXRuntimeError(f"{name} must be from {minimum} through {maximum}.")
    return value


def _env_optional_bool(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "on", "yes"}:
        return True
    if value in {"0", "false", "off", "no"}:
        return False
    raise VFXRuntimeError(f"{name} must be true/on or false/off.")


def _loopback_only(base_url: str) -> str:
    value = str(base_url).strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise VFXRuntimeError(
            "VFX runtime only permits a loopback llama-server URL."
        )
    if (
        parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise VFXRuntimeError(
            "VFX base URL must contain only scheme, host, and optional port."
        )
    return value


def _compact_description(definition: Mapping[str, Any]) -> str:
    function = definition.get("function", {})
    if not isinstance(function, Mapping):
        return ""
    description = function.get("description", "")
    if not isinstance(description, str):
        return ""
    return re.sub(r"\s+", " ", description).strip()[:220]


def _parameter_names(definition: Mapping[str, Any]) -> tuple[str, ...]:
    function = definition.get("function", {})
    if not isinstance(function, Mapping):
        return ()
    parameters = function.get("parameters", {})
    if not isinstance(parameters, Mapping):
        return ()
    properties = parameters.get("properties", {})
    if not isinstance(properties, Mapping):
        return ()
    return tuple(str(key) for key in properties.keys())
_JSON_SCHEMA_KEYS = {
    "type",
    "properties",
    "required",
    "items",
    "enum",
    "const",
    "anyOf",
    "oneOf",
    "allOf",
    "not",
    "additionalProperties",
    "patternProperties",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "pattern",
    "format",
    "nullable",
    "$ref",
    "$defs",
    "definitions",
    "dependentRequired",
    "minProperties",
    "maxProperties",
}


def _compact_schema(value: Any, description_chars: int) -> Any:
    """Preserve callable JSON-Schema semantics while dropping verbose metadata."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            key_str = str(key)
            if key_str == "description":
                if description_chars <= 0:
                    continue
                if isinstance(child, str):
                    result[key_str] = re.sub(r"\s+", " ", child).strip()[:description_chars]
                continue
            # These schema fields are themselves maps keyed by arbitrary names.
            # Their keys are semantic data and must NOT be filtered through the
            # top-level JSON-schema keyword allowlist.
            if key_str in ("properties", "patternProperties", "$defs", "definitions"):
                if isinstance(child, Mapping):
                    result[key_str] = {
                        str(map_key): _compact_schema(map_value, description_chars)
                        for map_key, map_value in child.items()
                    }
                else:
                    result[key_str] = child
                continue
            if key_str not in _JSON_SCHEMA_KEYS:
                continue
            result[key_str] = _compact_schema(child, description_chars)
        return result
    if isinstance(value, list):
        return [_compact_schema(item, description_chars) for item in value]
    return value


def _compact_tool_definition(
    definition: Mapping[str, Any],
    *,
    function_description_chars: int = DEFAULT_TOOL_DESCRIPTION_CHARS,
    property_description_chars: int = DEFAULT_PROPERTY_DESCRIPTION_CHARS,
) -> Mapping[str, Any]:
    """Return a compact OpenAI-compatible definition for one tool."""
    function = definition.get("function", {})
    if not isinstance(function, Mapping):
        return dict(definition)
    name = function.get("name")
    if not isinstance(name, str) or not name:
        return dict(definition)
    description = function.get("description", "")
    if isinstance(description, str) and function_description_chars > 0:
        compact_description = re.sub(r"\s+", " ", description).strip()[:function_description_chars]
    else:
        compact_description = ""
    parameters = function.get("parameters")
    if isinstance(parameters, Mapping):
        compact_parameters = _compact_schema(
            parameters,
            property_description_chars,
        )
    else:
        compact_parameters = {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }
    compact_function: dict[str, Any] = {
        "name": name,
        "description": compact_description,
        "parameters": compact_parameters,
    }
    if "strict" in function:
        compact_function["strict"] = function["strict"]
    return {
        "type": definition.get("type", "function"),
        "function": compact_function,
    }


def _approx_tokens(value: Any) -> int:
    """Conservative token estimate used for context-budget admission control."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return max(1, (len(encoded) + int(DEFAULT_TOKEN_ESTIMATE_CHARS) - 1) // int(DEFAULT_TOKEN_ESTIMATE_CHARS))


def _compact_result_text(
    text: str,
    limit: int = DEFAULT_TOOL_RESULT_MEMORY_CHARS,
) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    head = limit // 2
    tail = limit - head
    return (
        normalized[:head]
        + " ... [runtime compacted older evidence] ... "
        + normalized[-tail:]
    )


def _round_blocks(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group completed assistant/tool messages into execution rounds."""
    body = messages[2:]
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for message in body:
        content = message.get("content")
        if (
            message.get("role") == "system"
            and isinstance(content, str)
            and content.startswith(EXECUTION_MEMORY_MARKER)
        ):
            continue
        if message.get("role") == "assistant" and current:
            blocks.append(current)
            current = [message]
        else:
            current.append(message)
    if current:
        blocks.append(current)
    return blocks


def _execution_memory_message(
    old_blocks: list[list[dict[str, Any]]],
    existing_memory: str = "",
) -> Optional[str]:
    if not old_blocks and not existing_memory:
        return None
    lines = [EXECUTION_MEMORY_MARKER]
    if existing_memory:
        prior = existing_memory.split("\n", 1)[1] if "\n" in existing_memory else ""
        prior = prior.strip()
        if prior:
            lines.append(prior)
    for index, block in enumerate(old_blocks, start=1):
        lines.append(f"Prior execution round {index}:")
        for message in block:
            role = message.get("role")
            if role == "assistant":
                calls = message.get("tool_calls")
                if isinstance(calls, list):
                    for raw_call in calls:
                        if not isinstance(raw_call, Mapping):
                            continue
                        function = raw_call.get("function")
                        if not isinstance(function, Mapping):
                            continue
                        name = function.get("name", "?")
                        arguments = function.get("arguments", {})
                        try:
                            arg_text = json.dumps(
                                arguments,
                                ensure_ascii=False,
                                sort_keys=True,
                                default=str,
                            )
                        except (TypeError, ValueError):
                            arg_text = str(arguments)
                        lines.append(
                            f"  assistant tool call: {name} "
                            f"args={_compact_result_text(arg_text, 700)}"
                        )
            elif role == "tool":
                tool_id = message.get("tool_call_id", "?")
                content = message.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                lines.append(
                    f"  tool result [{tool_id}]: "
                    f"{_compact_result_text(content)}"
                )
    memory = "\n".join(lines)
    if len(memory) > 16000:
        memory = (
            memory[:8000]
            + "\n... [older execution memory compacted] ...\n"
            + memory[-8000:]
        )
    return memory


def _tool_call_id(raw_call: Mapping[str, Any]) -> str:
    value = raw_call.get("id")
    if isinstance(value, str) and value.strip():
        return value
    raise VFXProtocolError(
        "Model returned a tool call without a valid id."
    )


class VFXRuntime:
    """
    AI Director / DaVinci Resolve runtime.
    Existing external supervisor files are deliberately not imported or modified.
    The runtime is project-agnostic. It discovers the complete Resolve MCP surface
    exposed by llama-server and uses the canonical VFX Director prompt from
    prompts/VFXDirector.txt.
    Execution sees the complete discovered MCP tool surface directly. The runtime
    may compact schema metadata and older conversational evidence for context
    efficiency, but it does not pre-select or remove discovered tools.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        context_length: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        max_tool_rounds: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        config_path: Optional[str | os.PathLike[str]] = None,
        prompt_path: Optional[str | os.PathLike[str]] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        selected_config_path = (
            config_path
            if config_path is not None
            else os.environ.get(CONFIG_PATH_ENV)
        )
        self.config_path = (
            Path(selected_config_path).expanduser().resolve()
            if selected_config_path
            else DEFAULT_CONFIG_PATH
        )
        config = _load_runtime_config(self.config_path)
        config_base_url = _config_string(config, "base_url")
        config_model = _config_string(config, "model")
        config_context_length = _config_positive_int(config, "context_length")
        config_max_output_tokens = _config_positive_int(config, "max_output_tokens")
        config_max_tool_rounds = _config_nonnegative_int(config, "max_tool_rounds")
        config_timeout_seconds = _config_positive_float(config, "timeout_seconds")
        selected_base_url = (
            base_url
            if base_url is not None
            else os.environ.get(BASE_URL_ENV)
            or config_base_url
        )
        if not selected_base_url:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'base_url'."
            )
        self.base_url = _loopback_only(selected_base_url)
        self.model = (
            model
            if model is not None
            else os.environ.get(MODEL_ENV)
            or config_model
            or ""
        ).strip()
        if not self.model:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'model'."
            )
        if context_length is not None:
            self.context_length = context_length
        elif os.environ.get(CONTEXT_ENV):
            self.context_length = _env_int(
                CONTEXT_ENV,
                config_context_length or 1,
            )
        elif config_context_length is not None:
            self.context_length = config_context_length
        else:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'context_length'."
            )
        if max_output_tokens is not None:
            self.max_output_tokens = max_output_tokens
        elif os.environ.get(MAX_OUTPUT_ENV):
            self.max_output_tokens = _env_int(
                MAX_OUTPUT_ENV,
                config_max_output_tokens or 1,
            )
        elif config_max_output_tokens is not None:
            self.max_output_tokens = config_max_output_tokens
        else:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'max_output_tokens'."
            )
        if max_tool_rounds is not None:
            self.max_tool_rounds = max_tool_rounds
        elif os.environ.get(MAX_ROUNDS_ENV):
            self.max_tool_rounds = _env_nonnegative_int(
                MAX_ROUNDS_ENV,
                config_max_tool_rounds or 0,
            )
        elif config_max_tool_rounds is not None:
            self.max_tool_rounds = config_max_tool_rounds
        else:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'max_tool_rounds'."
            )
        if self.context_length <= 0:
            raise VFXRuntimeError(
                "context_length must be greater than zero."
            )
        if self.max_output_tokens <= 0:
            raise VFXRuntimeError(
                "max_output_tokens must be greater than zero."
            )
        if self.max_tool_rounds < 0:
            raise VFXRuntimeError(
                "max_tool_rounds must be zero or greater."
            )
        if self.max_output_tokens >= self.context_length:
            raise VFXRuntimeError(
                "max_output_tokens must be smaller than context_length."
            )
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        elif os.environ.get(TIMEOUT_ENV):
            self.timeout_seconds = _env_float(
                TIMEOUT_ENV,
                config_timeout_seconds or 0.0,
            )
        elif config_timeout_seconds is not None:
            self.timeout_seconds = config_timeout_seconds
        else:
            raise VFXRuntimeError(
                "VFX runtime configuration must define 'timeout_seconds'."
            )
        if self.timeout_seconds <= 0:
            raise VFXRuntimeError(
                "timeout_seconds must be greater than zero."
            )

        # Per-request sampling controls are supplied by the Electron settings layer.
        # If Electron is absent, fall back to the installed llama-server engine default.
        self.temperature = _env_bounded_float(TEMPERATURE_ENV, 0.8, 0.0, 1.0)
        self.top_p = _env_optional_float(TOP_P_ENV, 0.0, 1.0)
        self.top_k = _env_optional_int(TOP_K_ENV, 0, 1000)
        self.min_p = _env_optional_float(MIN_P_ENV, 0.0, 1.0)
        self.presence_penalty = _env_optional_float(PRESENCE_PENALTY_ENV, 0.0, 2.0)
        self.repetition_penalty = _env_optional_float(REPETITION_PENALTY_ENV, 0.0, 2.0)
        self.prompt_cache_reuse = _env_optional_bool(CACHE_PROMPT_ENV)
        self.context_overflow_policy = str(
            os.environ.get(CONTEXT_OVERFLOW_POLICY_ENV, CONTEXT_OVERFLOW_ROLLING)
        ).strip().lower()
        if self.context_overflow_policy not in {CONTEXT_OVERFLOW_ROLLING, CONTEXT_OVERFLOW_STOP}:
            raise VFXRuntimeError(
                "context overflow policy must be rolling_window or stop_at_limit."
            )

        selected_prompt_path = (
            prompt_path
            if prompt_path is not None
            else os.environ.get(DIRECTOR_PROMPT_ENV)
        )
        self.prompt_path = (
            Path(selected_prompt_path).expanduser().resolve()
            if selected_prompt_path
            else DEFAULT_PROMPT_PATH
        )
        self.director_prompt = self._load_director_prompt(
            self.prompt_path
        )
        self.session = session or requests.Session()
        self._tools: Optional[dict[str, VFXTool]] = None
        # Execution-governor state. The deadline covers the whole run_turn()
        # operation: model turns, MCP safety inspection, and tool calls.
        self._active_deadline: Optional[float] = None
        self._previous_round_fingerprint: Optional[str] = None
        self._identical_round_count = 0
        self._progress_callback: Optional[Callable[[Mapping[str, Any]], None]] = None
        self._execution_started_monotonic: Optional[float] = None
        self._telemetry: dict[str, Any] = {}
        # None = unknown/not probed; True = exact llama-server input-token endpoint
        # available; False = unavailable, so admission falls back to the conservative
        # local estimator.
        self._chat_input_tokens_supported: Optional[bool] = None
        self._last_exact_input_tokens: Optional[int] = None

    @staticmethod
    def _load_director_prompt(path: Path) -> str:
        try:
            content = path.read_text(
                encoding="utf-8",
            )
        except OSError as exc:
            raise VFXRuntimeError(
                f"AI Director prompt could not be read: {path}"
            ) from exc
        content = content.strip()
        if not content:
            raise VFXRuntimeError(
                f"AI Director prompt is empty: {path}"
            )
        return content

    @property
    def chat_endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    @property
    def chat_input_tokens_endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions/input_tokens"

    @property
    def tools_endpoint(self) -> str:
        return f"{self.base_url}/tools"

    def _exact_chat_input_tokens(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[Mapping[str, Any]],
    ) -> Optional[int]:
        """Ask llama-server to count the exact templated chat+tool input."""
        if self._chat_input_tokens_supported is False:
            return None
        body = {
            "model": self.model,
            "messages": messages,
            "tools": tool_definitions,
            "tool_choice": "auto",
            "parallel_tool_calls": True,
        }
        try:
            payload = self._request(
                "POST",
                self.chat_input_tokens_endpoint,
                json=body,
            )
        except VFXServerError as exc:
            # Capability probing must never make execution fail. A 404 means the
            # running llama-server predates this endpoint. Transient endpoint errors
            # fall back for this count but do not permanently disable future probes.
            if "HTTP 404" in str(exc):
                self._chat_input_tokens_supported = False
            return None
        except (VFXProtocolError, VFXContextLimitError):
            return None
        if not isinstance(payload, Mapping):
            self._chat_input_tokens_supported = False
            return None
        value = payload.get("input_tokens")
        try:
            count = int(value)
        except (TypeError, ValueError):
            self._chat_input_tokens_supported = False
            return None
        if count <= 0:
            self._chat_input_tokens_supported = False
            return None
        self._chat_input_tokens_supported = True
        self._last_exact_input_tokens = count
        return count

    def _admission_input_tokens(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[Mapping[str, Any]],
        *,
        exact_preferred: bool = True,
    ) -> tuple[int, str]:
        if exact_preferred:
            exact = self._exact_chat_input_tokens(messages, tool_definitions)
            if exact is not None:
                return exact, "llama_input_tokens"
        return (
            _approx_tokens(messages) + _approx_tokens(tool_definitions),
            "conservative_projection",
        )

    def _execution_sampling_parameters(self) -> dict[str, Any]:
        params: dict[str, Any] = {"temperature": self.temperature}
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        if self.min_p is not None:
            params["min_p"] = self.min_p
        if self.presence_penalty is not None:
            params["presence_penalty"] = self.presence_penalty
        if self.repetition_penalty is not None:
            params["repeat_penalty"] = self.repetition_penalty
        if self.prompt_cache_reuse is not None:
            params["cache_prompt"] = self.prompt_cache_reuse
        return params

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        if self._active_deadline is None:
            request_timeout = self.timeout_seconds
        else:
            request_timeout = self._remaining_execution_time()
        kwargs.setdefault("timeout", request_timeout)
        kwargs.setdefault("allow_redirects", False)
        try:
            response = self.session.request(
                method,
                url,
                **kwargs,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            if (
                self._active_deadline is not None
                and time.monotonic() >= self._active_deadline
            ):
                raise VFXExecutionTimeoutError(
                    "VFX execution deadline exceeded while waiting for "
                    f"the server: {url}"
                ) from exc
            raise VFXServerError(
                f"VFX server request timed out: {url}"
            ) from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body_text = exc.response.text.strip() if exc.response is not None else ""
            if status == 400 and re.search(
                r"exceeds the available context size|context size|too many tokens",
                body_text,
                re.IGNORECASE,
            ):
                raise VFXContextLimitError(
                    f"VFX server rejected the request because it exceeds the available "
                    f"context size: {body_text or exc}"
                ) from exc
            detail = body_text[:2000] if body_text else str(exc)
            raise VFXServerError(
                f"VFX server HTTP {status} request failed: {url}: {detail}"
            ) from exc
        except requests.RequestException as exc:
            raise VFXServerError(
                f"VFX server request failed: {url}: {exc}"
            ) from exc
        try:
            return response.json()
        except ValueError as exc:
            raise VFXProtocolError(
                f"VFX server returned invalid JSON: {url}"
            ) from exc

    @staticmethod
    def _metric_int(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _metric_float(value: Any) -> float:
        if isinstance(value, bool):
            return 0.0
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def _elapsed_ms(self) -> int:
        if self._execution_started_monotonic is None:
            return 0
        return max(0, int((time.monotonic() - self._execution_started_monotonic) * 1000.0))

    def _context_configuration(self) -> dict[str, Any]:
        prompt_budget = max(
            0,
            self.context_length
            - self.max_output_tokens
            - DEFAULT_CONTEXT_SAFETY_MARGIN_TOKENS,
        )
        return {
            "version": CONTEXT_TELEMETRY_VERSION,
            "context_window_tokens": self.context_length,
            "max_output_tokens": self.max_output_tokens,
            "safety_margin_tokens": DEFAULT_CONTEXT_SAFETY_MARGIN_TOKENS,
            "prompt_budget_tokens": prompt_budget,
            "overflow_policy": self.context_overflow_policy,
        }

    @staticmethod
    def _context_percent(used_tokens: int, context_window_tokens: int) -> Optional[float]:
        if context_window_tokens <= 0:
            return None
        return round((max(0, used_tokens) / context_window_tokens) * 100.0, 2)

    def _session_projection_tokens_from_messages(self, messages: Any) -> int:
        if not isinstance(messages, list) or len(messages) < 2:
            return 0
        user_message = messages[-1] if isinstance(messages[-1], Mapping) else None
        if not isinstance(user_message, Mapping) or user_message.get("role") != "user":
            return 0
        content = user_message.get("content")
        if not isinstance(content, str) or not content.startswith(SESSION_CONTEXT_MARKER):
            return 0
        marker = "\n\nCURRENT USER REQUEST\n"
        session_text = content.split(marker, 1)[0] if marker in content else content
        return _approx_tokens(session_text)

    def _projected_context_status(
        self,
        body: Mapping[str, Any],
        *,
        role: str,
        call_index: int,
        round_index: Optional[int],
    ) -> dict[str, Any]:
        messages = body.get("messages")
        tools = body.get("tools")
        message_tokens = _approx_tokens(messages) if isinstance(messages, list) else 0
        tool_tokens = _approx_tokens(tools) if isinstance(tools, list) and tools else 0
        projected_prompt_tokens = message_tokens + tool_tokens
        config = self._context_configuration()
        context_window = self._metric_int(config.get("context_window_tokens"))
        prompt_budget = self._metric_int(config.get("prompt_budget_tokens"))
        return {
            **config,
            "source": "conservative_projection",
            "exact": False,
            "role": role,
            "call_index": call_index,
            "round": round_index,
            "used_tokens": projected_prompt_tokens,
            "used_percent": self._context_percent(projected_prompt_tokens, context_window),
            "headroom_tokens": max(0, context_window - projected_prompt_tokens),
            "prompt_tokens": None,
            "completion_tokens": None,
            "cached_prompt_tokens": None,
            "evaluated_prompt_tokens": None,
            "projected_prompt_tokens": projected_prompt_tokens,
            "projected_prompt_percent": self._context_percent(projected_prompt_tokens, context_window),
            "admission_headroom_tokens": prompt_budget - projected_prompt_tokens,
            "message_tokens_estimate": message_tokens,
            "tool_schema_tokens_estimate": tool_tokens,
            "session_projection_tokens_estimate": self._session_projection_tokens_from_messages(messages),
        }

    def _actual_context_status(
        self,
        *,
        role: str,
        call_index: int,
        round_index: Optional[int],
        usage: Mapping[str, Any],
        timings: Mapping[str, Any],
    ) -> dict[str, Any]:
        prompt_tokens = self._metric_int(usage.get("prompt_tokens"))
        completion_tokens = self._metric_int(usage.get("completion_tokens"))
        total_tokens = self._metric_int(usage.get("total_tokens"))
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        prompt_details = usage.get("prompt_tokens_details")
        cached_tokens = 0
        if isinstance(prompt_details, Mapping):
            cached_tokens = self._metric_int(prompt_details.get("cached_tokens"))
        if cached_tokens == 0:
            cached_tokens = self._metric_int(timings.get("cache_n"))
        evaluated_prompt_tokens = self._metric_int(timings.get("prompt_n"))
        if evaluated_prompt_tokens == 0 and prompt_tokens >= cached_tokens:
            evaluated_prompt_tokens = prompt_tokens - cached_tokens
        config = self._context_configuration()
        context_window = self._metric_int(config.get("context_window_tokens"))
        prompt_budget = self._metric_int(config.get("prompt_budget_tokens"))
        if prompt_tokens <= 0 and total_tokens <= 0:
            last = self._telemetry.get("context_last")
            if isinstance(last, Mapping):
                fallback = dict(last)
                fallback.update({
                    **config,
                    "source": "projection_fallback",
                    "exact": False,
                    "role": role,
                    "call_index": call_index,
                    "round": round_index,
                })
                return fallback
        return {
            **config,
            "source": "llama_usage",
            "exact": True,
            "role": role,
            "call_index": call_index,
            "round": round_index,
            "used_tokens": total_tokens,
            "used_percent": self._context_percent(total_tokens, context_window),
            "headroom_tokens": max(0, context_window - total_tokens),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_prompt_tokens": cached_tokens,
            "evaluated_prompt_tokens": evaluated_prompt_tokens,
            "projected_prompt_tokens": None,
            "projected_prompt_percent": None,
            "admission_headroom_tokens": prompt_budget - prompt_tokens,
            "message_tokens_estimate": None,
            "tool_schema_tokens_estimate": None,
            "session_projection_tokens_estimate": None,
        }

    def _record_context_status(self, status: Mapping[str, Any]) -> dict[str, Any]:
        recorded = dict(status)
        used_tokens = self._metric_int(recorded.get("used_tokens"))
        prompt_tokens = self._metric_int(recorded.get("prompt_tokens"))
        projected_prompt_tokens = self._metric_int(recorded.get("projected_prompt_tokens"))
        if recorded.get("exact") is True:
            self._telemetry["context_peak_used_tokens"] = max(
                self._metric_int(self._telemetry.get("context_peak_used_tokens")),
                used_tokens,
            )
            self._telemetry["context_peak_prompt_tokens"] = max(
                self._metric_int(self._telemetry.get("context_peak_prompt_tokens")),
                prompt_tokens,
            )
        else:
            self._telemetry["context_peak_projected_prompt_tokens"] = max(
                self._metric_int(self._telemetry.get("context_peak_projected_prompt_tokens")),
                projected_prompt_tokens,
            )
        recorded["peak_used_tokens"] = self._metric_int(self._telemetry.get("context_peak_used_tokens"))
        recorded["peak_prompt_tokens"] = self._metric_int(self._telemetry.get("context_peak_prompt_tokens"))
        recorded["peak_projected_prompt_tokens"] = self._metric_int(
            self._telemetry.get("context_peak_projected_prompt_tokens")
        )
        recorded["peak_used_percent"] = self._context_percent(
            recorded["peak_used_tokens"],
            self.context_length,
        )
        self._telemetry["context_last"] = recorded
        return recorded

    def _emit_context_status(self, status: Mapping[str, Any]) -> dict[str, Any]:
        recorded = self._record_context_status(status)
        self._emit_progress("context_status", context=recorded)
        return recorded

    def _emit_progress(self, kind: str, **fields: Any) -> None:
        callback = self._progress_callback
        if callback is None:
            return
        payload: dict[str, Any] = {
            "kind": kind,
            "elapsed_ms": self._elapsed_ms(),
            **fields,
        }
        try:
            callback(payload)
        except Exception:
            # UI/IPC telemetry must never be able to break model execution.
            pass

    def _reset_telemetry(self) -> None:
        self._telemetry = {
            "model_calls": 0,
            "tool_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cached_prompt_tokens": 0,
            "evaluated_prompt_tokens": 0,
            "prompt_ms": 0.0,
            "generation_ms": 0.0,
            "timed_generated_tokens": 0,
            "first_model_output_ms": None,
            "context_peak_used_tokens": 0,
            "context_peak_prompt_tokens": 0,
            "context_peak_projected_prompt_tokens": 0,
            "context_compactions": 0,
            "context_compacted_turns": 0,
            "context_compaction_before_tokens": 0,
            "context_compaction_after_tokens": 0,
            "context_admission_tokens": 0,
            "context_admission_source": "unmeasured",
            "context_prompt_budget_tokens": 0,
            "context_last": {
                **self._context_configuration(),
                "source": "configured",
                "exact": False,
                "used_tokens": 0,
                "used_percent": 0.0,
                "headroom_tokens": self.context_length,
                "peak_used_tokens": 0,
                "peak_prompt_tokens": 0,
                "peak_used_percent": 0.0,
            },
        }

    def _telemetry_summary(self, *, status: str = "running") -> dict[str, Any]:
        telemetry = self._telemetry
        prompt_ms = self._metric_float(telemetry.get("prompt_ms"))
        generation_ms = self._metric_float(telemetry.get("generation_ms"))
        evaluated_prompt_tokens = self._metric_int(telemetry.get("evaluated_prompt_tokens"))
        timed_generated_tokens = self._metric_int(telemetry.get("timed_generated_tokens"))
        prompt_tokens = self._metric_int(telemetry.get("prompt_tokens"))
        cached_prompt_tokens = self._metric_int(telemetry.get("cached_prompt_tokens"))
        return {
            "status": status,
            "elapsed_ms": self._elapsed_ms(),
            "model_calls": self._metric_int(telemetry.get("model_calls")),
            "tool_calls": self._metric_int(telemetry.get("tool_calls")),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": self._metric_int(telemetry.get("completion_tokens")),
            "total_tokens": self._metric_int(telemetry.get("total_tokens")),
            "cached_prompt_tokens": cached_prompt_tokens,
            "evaluated_prompt_tokens": evaluated_prompt_tokens,
            "cache_reuse_percent": (
                round((cached_prompt_tokens / prompt_tokens) * 100.0, 1)
                if prompt_tokens > 0
                else None
            ),
            "prompt_tokens_per_second": (
                round((evaluated_prompt_tokens * 1000.0) / prompt_ms, 2)
                if prompt_ms > 0 and evaluated_prompt_tokens > 0
                else None
            ),
            "generation_tokens_per_second": (
                round((timed_generated_tokens * 1000.0) / generation_ms, 2)
                if generation_ms > 0 and timed_generated_tokens > 0
                else None
            ),
            "first_model_output_ms": telemetry.get("first_model_output_ms"),
            "context_compactions": self._metric_int(telemetry.get("context_compactions")),
            "context_compacted_turns": self._metric_int(telemetry.get("context_compacted_turns")),
            "context_compaction_before_tokens": self._metric_int(telemetry.get("context_compaction_before_tokens")),
            "context_compaction_after_tokens": self._metric_int(telemetry.get("context_compaction_after_tokens")),
            "context_admission_tokens": self._metric_int(telemetry.get("context_admission_tokens")),
            "context_admission_source": str(telemetry.get("context_admission_source") or "unmeasured"),
            "context_prompt_budget_tokens": self._metric_int(telemetry.get("context_prompt_budget_tokens")),
            "context": dict(telemetry.get("context_last"))
            if isinstance(telemetry.get("context_last"), Mapping)
            else self._context_configuration(),
        }

    def _start_model_call(self, role: str, round_index: Optional[int]) -> int:
        self._telemetry["model_calls"] = self._metric_int(self._telemetry.get("model_calls")) + 1
        call_index = self._telemetry["model_calls"]
        self._emit_progress(
            "model_call_start",
            role=role,
            call_index=call_index,
            round=round_index,
        )
        return call_index

    def _finish_model_call(
        self,
        *,
        role: str,
        call_index: int,
        round_index: Optional[int],
        usage: Any,
        timings: Any,
    ) -> None:
        usage_map = usage if isinstance(usage, Mapping) else {}
        timings_map = timings if isinstance(timings, Mapping) else {}

        prompt_tokens = self._metric_int(usage_map.get("prompt_tokens"))
        completion_tokens = self._metric_int(usage_map.get("completion_tokens"))
        total_tokens = self._metric_int(usage_map.get("total_tokens"))
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens

        prompt_details = usage_map.get("prompt_tokens_details")
        cached_tokens = 0
        if isinstance(prompt_details, Mapping):
            cached_tokens = self._metric_int(prompt_details.get("cached_tokens"))
        if cached_tokens == 0:
            cached_tokens = self._metric_int(timings_map.get("cache_n"))

        evaluated_prompt_tokens = self._metric_int(timings_map.get("prompt_n"))
        if evaluated_prompt_tokens == 0 and prompt_tokens >= cached_tokens:
            evaluated_prompt_tokens = prompt_tokens - cached_tokens

        predicted_n = self._metric_int(timings_map.get("predicted_n"))
        if predicted_n == 0:
            predicted_n = completion_tokens

        self._telemetry["prompt_tokens"] += prompt_tokens
        self._telemetry["completion_tokens"] += completion_tokens
        self._telemetry["total_tokens"] += total_tokens
        self._telemetry["cached_prompt_tokens"] += cached_tokens
        self._telemetry["evaluated_prompt_tokens"] += evaluated_prompt_tokens
        self._telemetry["prompt_ms"] += self._metric_float(timings_map.get("prompt_ms"))
        self._telemetry["generation_ms"] += self._metric_float(timings_map.get("predicted_ms"))
        self._telemetry["timed_generated_tokens"] += predicted_n

        context_status = self._actual_context_status(
            role=role,
            call_index=call_index,
            round_index=round_index,
            usage=usage_map,
            timings=timings_map,
        )
        self._emit_context_status(context_status)

        self._emit_progress(
            "model_call_complete",
            role=role,
            call_index=call_index,
            round=round_index,
            usage=dict(usage_map),
            timings=dict(timings_map),
            summary=self._telemetry_summary(),
        )

    def _chat_completion_request(
        self,
        body: Mapping[str, Any],
        *,
        model_call_role: str = "execution",
        round_index: Optional[int] = None,
    ) -> Mapping[str, Any]:
        """Execute one streamed model call with native llama-server telemetry."""
        if self._active_deadline is None:
            request_timeout = self.timeout_seconds
        else:
            request_timeout = self._remaining_execution_time()

        call_index = self._start_model_call(model_call_role, round_index)
        request_body = dict(body)
        request_body["stream"] = True
        stream_options = request_body.get("stream_options")
        if not isinstance(stream_options, Mapping):
            stream_options = {}
        request_body["stream_options"] = {**dict(stream_options), "include_usage": True}
        request_body["return_progress"] = True
        self._emit_context_status(
            self._projected_context_status(
                request_body,
                role=model_call_role,
                call_index=call_index,
                round_index=round_index,
            )
        )

        try:
            response = self.session.request(
                "POST",
                self.chat_endpoint,
                json=request_body,
                timeout=request_timeout,
                allow_redirects=False,
                stream=True,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            if (
                self._active_deadline is not None
                and time.monotonic() >= self._active_deadline
            ):
                raise VFXExecutionTimeoutError(
                    "VFX execution deadline exceeded while waiting for "
                    f"the server: {self.chat_endpoint}"
                ) from exc
            raise VFXServerError(
                f"VFX server request timed out: {self.chat_endpoint}"
            ) from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body_text = exc.response.text.strip() if exc.response is not None else ""
            if status == 400 and re.search(
                r"exceeds the available context size|context size|too many tokens",
                body_text,
                re.IGNORECASE,
            ):
                raise VFXContextLimitError(
                    "VFX server rejected the request because it exceeds the available "
                    f"context size: {body_text or exc}"
                ) from exc
            detail = body_text[:2000] if body_text else str(exc)
            raise VFXServerError(
                f"VFX server HTTP {status} request failed: {self.chat_endpoint}: {detail}"
            ) from exc
        except requests.RequestException as exc:
            raise VFXServerError(
                f"VFX server request failed: {self.chat_endpoint}: {exc}"
            ) from exc

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}
        role = "assistant"
        finish_reason: Optional[str] = None
        usage: Any = None
        timings: Any = None
        generation_started = False
        try:
            for raw_line in response.iter_lines(decode_unicode=False):
                self._ensure_execution_budget()
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise VFXProtocolError(
                        "VFX server returned an invalid SSE JSON chunk."
                    ) from exc
                if not isinstance(chunk, Mapping):
                    raise VFXProtocolError(
                        "VFX server returned a non-object SSE chunk."
                    )
                if isinstance(chunk.get("error"), Mapping):
                    raise VFXServerError(
                        f"VFX server returned an error during streaming: {json.dumps(chunk['error'], ensure_ascii=False)}"
                    )
                prompt_progress = chunk.get("prompt_progress")
                if isinstance(prompt_progress, Mapping):
                    total = self._metric_int(prompt_progress.get("total"))
                    cache = self._metric_int(prompt_progress.get("cache"))
                    processed = self._metric_int(prompt_progress.get("processed"))
                    progress_time_ms = self._metric_float(prompt_progress.get("time_ms"))
                    overall_percent = (processed / total * 100.0) if total > 0 else None
                    timed_total = max(0, total - cache)
                    timed_processed = max(0, processed - cache)
                    timed_percent = (timed_processed / timed_total * 100.0) if timed_total > 0 else None
                    self._emit_progress(
                        "prompt_progress",
                        role=model_call_role,
                        call_index=call_index,
                        round=round_index,
                        total=total,
                        cache=cache,
                        processed=processed,
                        time_ms=progress_time_ms,
                        percent=round(overall_percent, 2) if overall_percent is not None else None,
                        timed_percent=round(timed_percent, 2) if timed_percent is not None else None,
                    )
                raw_choices = chunk.get("choices")
                if isinstance(chunk.get("usage"), Mapping):
                    usage = chunk["usage"]
                if isinstance(chunk.get("timings"), Mapping):
                    timings = chunk["timings"]
                if not isinstance(raw_choices, list) or not raw_choices:
                    continue
                choice = raw_choices[0]
                if not isinstance(choice, Mapping):
                    raise VFXProtocolError(
                        "VFX server returned a non-object streaming choice."
                    )
                if isinstance(choice.get("finish_reason"), str):
                    finish_reason = choice["finish_reason"]
                delta = choice.get("delta")
                if not isinstance(delta, Mapping):
                    continue
                if not generation_started:
                    has_generation_output = (
                        isinstance(delta.get("content"), str) and bool(delta.get("content"))
                    ) or (
                        isinstance(delta.get("reasoning_content"), str) and bool(delta.get("reasoning_content"))
                    ) or bool(delta.get("tool_calls"))
                    if has_generation_output:
                        generation_started = True
                        if self._telemetry.get("first_model_output_ms") is None:
                            self._telemetry["first_model_output_ms"] = self._elapsed_ms()
                        self._emit_progress(
                            "generation_start",
                            role=model_call_role,
                            call_index=call_index,
                            round=round_index,
                        )
                if isinstance(delta.get("role"), str):
                    role = delta["role"]
                content = delta.get("content")
                if isinstance(content, str):
                    content_parts.append(content)
                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str):
                    reasoning_parts.append(reasoning)
                raw_tool_calls = delta.get("tool_calls")
                if raw_tool_calls is None:
                    continue
                if not isinstance(raw_tool_calls, list):
                    raise VFXProtocolError(
                        "Streaming assistant.tool_calls must be an array."
                    )
                for raw_call in raw_tool_calls:
                    if not isinstance(raw_call, Mapping):
                        raise VFXProtocolError(
                            "Streaming tool call is not an object."
                        )
                    raw_index = raw_call.get("index", 0)
                    try:
                        index = int(raw_index)
                    except (TypeError, ValueError) as exc:
                        raise VFXProtocolError(
                            "Streaming tool call index is not an integer."
                        ) from exc
                    call = tool_calls.setdefault(
                        index,
                        {
                            "id": None,
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if isinstance(raw_call.get("id"), str):
                        call["id"] = raw_call["id"]
                    if isinstance(raw_call.get("type"), str):
                        call["type"] = raw_call["type"]
                    function_delta = raw_call.get("function")
                    if not isinstance(function_delta, Mapping):
                        continue
                    if isinstance(function_delta.get("name"), str):
                        call["function"]["name"] = call["function"].get("name", "") + function_delta["name"]
                    if isinstance(function_delta.get("arguments"), str):
                        call["function"]["arguments"] = call["function"].get("arguments", "") + function_delta["arguments"]
        except requests.Timeout as exc:
            if (
                self._active_deadline is not None
                and time.monotonic() >= self._active_deadline
            ):
                raise VFXExecutionTimeoutError(
                    "VFX execution deadline exceeded while reading the streaming response."
                ) from exc
            raise VFXServerError(
                "VFX server streaming response timed out."
            ) from exc
        except requests.RequestException as exc:
            raise VFXServerError(
                f"VFX server streaming request failed: {exc}"
            ) from exc
        finally:
            response.close()

        message: dict[str, Any] = {
            "role": role,
            "content": "".join(content_parts),
        }
        if reasoning_parts:
            message["reasoning_content"] = "".join(reasoning_parts)
        if tool_calls:
            message["tool_calls"] = [
                tool_calls[index]
                for index in sorted(tool_calls)
            ]
        result: dict[str, Any] = {
            "choices": [
                {
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ]
        }
        if usage is not None:
            result["usage"] = usage
        if timings is not None:
            result["timings"] = timings
        self._finish_model_call(
            role=model_call_role,
            call_index=call_index,
            round_index=round_index,
            usage=usage,
            timings=timings,
        )
        return result

    def _begin_execution(
        self,
        progress_callback: Optional[Callable[[Mapping[str, Any]], None]] = None,
    ) -> None:
        self._execution_started_monotonic = time.monotonic()
        self._progress_callback = progress_callback
        self._reset_telemetry()
        self._active_deadline = self._execution_started_monotonic + self.timeout_seconds
        self._previous_round_fingerprint = None
        self._identical_round_count = 0

    def _clear_execution(self) -> None:
        self._active_deadline = None
        self._previous_round_fingerprint = None
        self._identical_round_count = 0
        self._progress_callback = None
        self._execution_started_monotonic = None

    def _remaining_execution_time(self) -> float:
        if self._active_deadline is None:
            return self.timeout_seconds
        remaining = self._active_deadline - time.monotonic()
        if remaining <= 0:
            raise VFXExecutionTimeoutError(
                f"VFX execution deadline exceeded ({self.timeout_seconds:g} seconds)."
            )
        return max(remaining, 0.001)

    def _ensure_execution_budget(self) -> None:
        self._remaining_execution_time()

    @staticmethod
    def _round_fingerprint(
        calls: list[VFXToolCall],
        results: list[str],
    ) -> str:
        payload = [
            {
                "tool": call.tool_name,
                "arguments": dict(call.arguments),
                "result": result,
            }
            for call, result in zip(calls, results)
        ]
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _record_round_progress(
        self,
        calls: list[VFXToolCall],
        results: list[str],
    ) -> Optional[str]:
        """
        Detect repeated identical work and return a non-fatal recovery notice.
        Repetition is not treated as a runtime failure. The notice is injected
        into the persistent system instruction so the model can change strategy,
        use a different read, or finish from evidence already collected. The
        whole-run deadline remains the actual liveness boundary.
        """
        if not calls:
            return None
        fingerprint = self._round_fingerprint(calls, results)
        if fingerprint == self._previous_round_fingerprint:
            self._identical_round_count += 1
        else:
            self._previous_round_fingerprint = fingerprint
            self._identical_round_count = 1
        if self._identical_round_count < DEFAULT_IDENTICAL_ROUND_STALL_THRESHOLD:
            return None
        tool_names = ", ".join(call.tool_name for call in calls)
        repetition_count = self._identical_round_count
        # Reset after intervention. If the model ignores the notice, another
        # intervention may be issued later, but execution is never killed merely
        # because the model repeated work.
        self._previous_round_fingerprint = None
        self._identical_round_count = 0
        return (
            "The runtime detected repeated identical tool work. "
            f"The same complete tool-operation round has repeated {repetition_count} "
            f"times: {tool_names}. Do NOT repeat that same tool-operation round "
            "again unless new state or changed arguments make it necessary. "
            "Reassess the remaining user request. Use a different available Resolve "
            "read when additional evidence is genuinely needed, or synthesize the "
            "answer from evidence already collected when the requested fact is "
            "established. This is a recovery notice, not a failure."
        )

    def discover_tools(
        self,
        *,
        refresh: bool = False,
    ) -> dict[str, VFXTool]:
        if self._tools is not None and not refresh:
            return self._tools
        payload = self._request(
            "GET",
            self.tools_endpoint,
        )
        if not isinstance(payload, list):
            raise VFXProtocolError(
                "GET /tools did not return a JSON array."
            )
        discovered: dict[str, VFXTool] = {}
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            name = item.get("tool")
            if not isinstance(name, str):
                continue
            if not (
                name.startswith("davinci-resolve_")
                or name.startswith("davinci-resolve-full_")
                or name.startswith("davinci-resolve-advanced_")
            ):
                continue
            if item.get("type") != "mcp":
                continue
            definition = item.get("definition")
            if not isinstance(definition, Mapping):
                continue
            discovered[name] = VFXTool(
                name=name,
                definition=dict(definition),
                display_name=str(
                    item.get("display_name") or name
                ),
                description=_compact_description(definition),
                parameter_names=_parameter_names(definition),
            )
        if not discovered:
            raise VFXServerError(
                "No davinci-resolve MCP tools were discovered."
            )
        self._tools = discovered
        return discovered

    def _semantic_model_tool_definitions(
        self,
        *,
        property_description_chars: int = MODEL_PROPERTY_DESCRIPTION_CHARS,
    ) -> list[Mapping[str, Any]]:
        """Return the distinct semantic MCP capability surfaces for the model.

        discover_tools() continues to retain the complete compound + granular +
        advanced inventory for execution authorization. Model prompt exposure is
        limited to live compound/default tools and unique advanced/offline tools.
        The granular --full interface is redundant with compound live-API coverage
        and remains registered/discovered for diagnostics/compatibility without
        consuming every model request.
        """
        available = self.discover_tools()
        semantic = [
            tool
            for name, tool in sorted(available.items())
            if (
                name.startswith(MODEL_COMPOUND_PREFIX)
                or name.startswith(MODEL_ADVANCED_PREFIX)
            )
        ]
        if not any(
            tool.name.startswith(MODEL_COMPOUND_PREFIX)
            for tool in semantic
        ):
            raise VFXServerError(
                "No davinci-resolve compound/default MCP tools were discovered."
            )
        if not any(
            tool.name.startswith(MODEL_ADVANCED_PREFIX)
            for tool in semantic
        ):
            raise VFXServerError(
                "No davinci-resolve advanced/offline MCP tools were discovered."
            )
        return [
            _compact_tool_definition(
                tool.definition,
                function_description_chars=MODEL_FUNCTION_DESCRIPTION_CHARS,
                property_description_chars=property_description_chars,
            )
            for tool in semantic
        ]

    def _all_tool_definitions(self) -> list[Mapping[str, Any]]:
        """Return semantic compound + advanced tool definitions for model use.

        The historical method name is retained for call-site compatibility.
        Runtime discovery and execution authorization still own the complete
        registered inventory, including hidden granular/full tool names.
        """
        available = self.discover_tools()
        source_identity = id(available)
        cached_identity = getattr(self, "_model_tool_definitions_source", None)
        cached_mode = getattr(self, "_model_tool_definition_mode", None)
        cached_definitions = getattr(self, "_model_tool_definitions", None)
        if (
            cached_definitions is not None
            and cached_identity == source_identity
            and cached_mode == "compound-advanced-semantic"
        ):
            return cached_definitions

        prompt_budget = (
            self.context_length
            - self.max_output_tokens
            - DEFAULT_CONTEXT_SAFETY_MARGIN_TOKENS
        )
        definitions = self._semantic_model_tool_definitions()
        if _approx_tokens(definitions) > prompt_budget:
            # Preserve function-level action catalogs while dropping nested
            # property prose first. The action catalogs carry the routing semantics.
            definitions = self._semantic_model_tool_definitions(
                property_description_chars=0,
            )
            if _approx_tokens(definitions) > prompt_budget:
                raise VFXContextLimitError(
                    "The semantic Resolve compound + advanced tool surface does not "
                    "fit inside the configured context. Increase context_length."
                )

        self._model_tool_definitions = definitions
        self._model_tool_definitions_source = source_identity
        self._model_tool_definition_mode = "compound-advanced-semantic"
        return definitions

    @staticmethod
    def _assistant_message(
        response: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VFXProtocolError(
                "Chat response lacks an assistant message."
            ) from exc
        if not isinstance(message, Mapping):
            raise VFXProtocolError(
                "Assistant message is not an object."
            )
        return message

    @staticmethod
    def _extract_calls(
        assistant: Mapping[str, Any],
    ) -> list[VFXToolCall]:
        raw_calls = assistant.get("tool_calls")
        if raw_calls is None:
            return []
        if not isinstance(raw_calls, list):
            raise VFXProtocolError(
                "assistant.tool_calls must be an array."
            )
        calls: list[VFXToolCall] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, Mapping):
                raise VFXProtocolError(
                    "Tool call is not an object."
                )
            function = raw_call.get("function")
            if not isinstance(function, Mapping):
                raise VFXProtocolError(
                    "Tool call lacks function object."
                )
            name = function.get("name")
            arguments = function.get("arguments")
            if not isinstance(name, str) or not name:
                raise VFXProtocolError(
                    "Tool call lacks a valid function name."
                )
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise VFXProtocolError(
                        f"Tool arguments were not valid JSON: {arguments!r}"
                    ) from exc
            if not isinstance(arguments, Mapping):
                raise VFXProtocolError(
                    f"Tool arguments for {name!r} must be an object."
                )
            calls.append(
                VFXToolCall(
                    _tool_call_id(raw_call),
                    name,
                    dict(arguments),
                )
            )
        return calls

    def _execute_tool(
        self,
        call: VFXToolCall,
    ) -> str:
        if call.tool_name not in self.discover_tools():
            raise VFXAuthorizationError(
                "Model requested undiscovered Resolve tool: "
                f"{call.tool_name}"
            )
        result = self._request(
            "POST",
            self.tools_endpoint,
            json={
                "tool": call.tool_name,
                "params": dict(call.arguments),
            },
        )
        if not isinstance(result, Mapping):
            raise VFXProtocolError(
                "Resolve tool returned a non-object result."
            )
        if result.get("error"):
            return json.dumps(
                {"error": result["error"]},
                ensure_ascii=False,
                default=str,
            )
        text = result.get("plain_text_response")
        if isinstance(text, str):
            return text
        return json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )

    @staticmethod
    def _rolling_session_split(user_content: str) -> tuple[str, str] | None:
        if not isinstance(user_content, str) or not user_content.startswith(SESSION_CONTEXT_MARKER):
            return None
        marker = "\n\nCURRENT USER REQUEST\n"
        if marker not in user_content:
            return None
        session_text, current_request = user_content.split(marker, 1)
        return session_text, current_request

    @staticmethod
    def _rolling_turn_retention(block: str) -> set[str]:
        match = re.search(r"(?mi)^Retention:\s*([^\n]+)", block or "")
        if not match:
            return {"ordinary"}
        values = {item.strip().lower() for item in match.group(1).split(",") if item.strip()}
        return values or {"ordinary"}

    @staticmethod
    def _rolling_compaction_level(block: str) -> str:
        if not block.startswith("COMPACT SESSION TURN "):
            return "full"
        match = re.search(r"(?mi)^Compaction:\s*([^\n]+)", block or "")
        return (match.group(1).strip().lower() if match else "compact")

    @staticmethod
    def _rolling_turn_field(block: str, label: str, next_labels: tuple[str, ...]) -> str:
        line_match = re.search(rf"(?mi)^{re.escape(label)}:\s*(.+)$", block or "")
        if line_match and not line_match.group(1).strip().startswith(("SESSION TURN", "COMPACT SESSION TURN")):
            return re.sub(r"\s+", " ", line_match.group(1).strip()).strip("'\"")
        marker = f"{label}:\n"
        start = (block or "").find(marker)
        if start < 0:
            return ""
        start += len(marker)
        ends = []
        for item in next_labels:
            pos = block.find(f"\n{item}:", start)
            if pos >= 0:
                ends.append(pos)
        end = min(ends) if ends else len(block)
        return re.sub(r"\s+", " ", block[start:end].strip())

    @staticmethod
    def _rolling_compact_turn(block: str) -> str:
        if VFXRuntime._rolling_compaction_level(block) != "full":
            return block
        first = re.search(r"(?m)^SESSION TURN\s+(\d+)\s*$", block)
        ordinal = first.group(1) if first else "?"
        retention = re.search(r"(?mi)^Retention:\s*([^\n]+)", block)
        status = re.search(r"(?mi)^Status:\s*([^\n]+)", block)
        runtime = re.search(r"(?mi)^Runtime:\s*([^\n]+)", block)

        classes = VFXRuntime._rolling_turn_retention(block)
        protected = bool(classes & {"uncertain", "mutation", "constraint"})
        user_limit = 1600 if protected else 900
        outcome_limit = 1200 if protected else 700
        tool_limit = 2200 if protected else 900
        user = VFXRuntime._rolling_turn_field(block, "User", ("AI Director",))[:user_limit]
        outcome = VFXRuntime._rolling_turn_field(block, "AI Director", ("Observed tool provenance",))[:outcome_limit]
        tools = VFXRuntime._rolling_turn_field(block, "Observed tool provenance", ())[:tool_limit]
        return "\n".join([
            f"COMPACT SESSION TURN {ordinal}",
            "Compaction: compact",
            f"Retention: {retention.group(1).strip() if retention else 'ordinary'}",
            f"Status: {status.group(1).strip() if status else 'unknown'}",
            f"Runtime: {runtime.group(1).strip() if runtime else 'unknown'}",
            f"User: {user!r}",
            f"Outcome: {outcome!r}",
            f"Tools: {tools!r}",
        ])

    @staticmethod
    def _rolling_minimal_turn(block: str) -> str:
        level = VFXRuntime._rolling_compaction_level(block)
        if level == "minimal":
            return block
        first = re.search(r"(?m)^(?:SESSION TURN|COMPACT SESSION TURN)\s+(\d+)\s*$", block or "")
        ordinal = first.group(1) if first else "?"
        retention = re.search(r"(?mi)^Retention:\s*([^\n]+)", block or "")
        status = re.search(r"(?mi)^Status:\s*([^\n]+)", block or "")
        runtime = re.search(r"(?mi)^Runtime:\s*([^\n]+)", block or "")
        classes = VFXRuntime._rolling_turn_retention(block)
        protected = bool(classes & {"uncertain", "mutation", "constraint"})
        user_limit = 520 if protected else 260
        outcome_limit = 420 if protected else 180
        tool_limit = 760 if protected else 240
        user = VFXRuntime._rolling_turn_field(block, "User", ("AI Director", "Outcome", "Observed tool provenance", "Tools"))[:user_limit]
        outcome = VFXRuntime._rolling_turn_field(block, "AI Director", ("Observed tool provenance",))
        if not outcome:
            outcome = VFXRuntime._rolling_turn_field(block, "Outcome", ("Tools",))
        tools = VFXRuntime._rolling_turn_field(block, "Observed tool provenance", ())
        if not tools:
            tools = VFXRuntime._rolling_turn_field(block, "Tools", ())
        return "\n".join([
            f"COMPACT SESSION TURN {ordinal}",
            "Compaction: minimal",
            f"Retention: {retention.group(1).strip() if retention else 'ordinary'}",
            f"Status: {status.group(1).strip() if status else 'unknown'}",
            f"Runtime: {runtime.group(1).strip() if runtime else 'unknown'}",
            f"User: {user!r}",
            f"Outcome: {outcome[:outcome_limit]!r}",
            f"Tools: {tools[:tool_limit]!r}",
        ])

    @staticmethod
    def _rolling_session_parts(session_text: str) -> tuple[str, str, list[str]] | None:
        origin_marker = "\n\nSESSION ORIGIN\n"
        if origin_marker not in session_text:
            return None
        header, origin_and_rest = session_text.split(origin_marker, 1)
        origin_text = "SESSION ORIGIN\n" + origin_and_rest
        matches = list(ROLLING_SESSION_TURN_RE.finditer(origin_text))
        if not matches:
            return header, origin_text, []
        origin = origin_text[:matches[0].start()].rstrip()
        turns: list[str] = []
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(origin_text)
            turns.append(origin_text[match.start():end].strip())
        return header, origin, turns

    def _fit_rolling_session_context(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[Mapping[str, Any]],
        *,
        round_index: Optional[int],
        stage: str,
        aggressive: bool = False,
    ) -> list[dict[str, Any]]:
        if self.context_overflow_policy != CONTEXT_OVERFLOW_ROLLING or len(messages) < 2:
            return messages
        user_content = messages[1].get("content") if isinstance(messages[1], Mapping) else None
        split = self._rolling_session_split(user_content) if isinstance(user_content, str) else None
        if split is None:
            return messages

        prompt_budget = self._context_configuration()["prompt_budget_tokens"]
        input_tokens, admission_source = self._admission_input_tokens(
            messages, tool_definitions, exact_preferred=True
        )
        self._telemetry["context_admission_tokens"] = input_tokens
        self._telemetry["context_admission_source"] = admission_source
        self._telemetry["context_prompt_budget_tokens"] = prompt_budget

        # Exact llama-server counting can target the real configured prompt budget.
        # Estimator fallback retains an additional margin only after a real server
        # rejection proves the estimate optimistic.
        target_input_tokens = prompt_budget
        if aggressive and admission_source != "llama_input_tokens":
            target_input_tokens = max(1024, int(prompt_budget * 0.90))

        estimated_now = input_tokens
        if estimated_now <= target_input_tokens and not aggressive:
            return messages

        session_text, current_request = split
        parsed = self._rolling_session_parts(session_text)
        if parsed is None:
            raise VFXContextLimitError(
                "Rolling Window could not parse AI Director session context safely. Clear/start a new session or switch Context Overflow to Stop at Limit."
            )
        header, origin, turns = parsed
        if not turns:
            return messages

        before_tokens = estimated_now
        rendered: list[str | None] = list(turns)
        protected_flags = [
            bool(self._rolling_turn_retention(block) & {"uncertain", "mutation", "constraint"})
            for block in turns
        ]
        status_values = []
        for block in turns:
            match = re.search(r"(?mi)^Status:\s*([^\n]+)", block or "")
            status_values.append(match.group(1).strip().lower() if match else "unknown")

        # Normal rolling protects the newest two turns from eviction. A real server
        # rejection may compact the second-newest turn, but the newest completed turn
        # remains verbatim unless the request is otherwise impossible.
        protected_tail = 1 if aggressive else 2
        recent_boundary = max(0, len(rendered) - ROLLING_MIN_FULL_RECENT_TURNS)
        compact_tail_boundary = max(0, len(rendered) - protected_tail)

        def rebuild() -> list[dict[str, Any]]:
            active = [item for item in rendered if item]
            session = "\n\n".join([header, origin, *active]).strip()
            content = session + "\n\nCURRENT USER REQUEST\n" + current_request
            candidate = [dict(item) for item in messages]
            candidate[1] = {**candidate[1], "content": content}
            return candidate

        candidate = rebuild()
        changed_indexes: set[int] = set()
        evicted_indexes: set[int] = set()

        def candidate_tokens() -> tuple[int, str]:
            return self._admission_input_tokens(
                candidate, tool_definitions, exact_preferred=True
            )

        def fits() -> bool:
            count, source = candidate_tokens()
            self._telemetry["context_admission_tokens"] = count
            self._telemetry["context_admission_source"] = source
            return count <= target_input_tokens

        def apply_transform(indexes: list[int], transform) -> bool:
            nonlocal candidate
            for index in indexes:
                current = rendered[index]
                if not current:
                    continue
                replacement = transform(current)
                if replacement == current:
                    continue
                rendered[index] = replacement
                changed_indexes.add(index)
                candidate = rebuild()
                if fits():
                    return True
            return fits()

        # Tier 1: full -> compact. Old ordinary history goes first, then protected
        # old history, then progressively newer history while preserving the tail.
        full_old_ordinary = [
            i for i in range(recent_boundary)
            if not protected_flags[i] and self._rolling_compaction_level(rendered[i] or "") == "full"
        ]
        full_old_protected = [
            i for i in range(recent_boundary)
            if protected_flags[i] and self._rolling_compaction_level(rendered[i] or "") == "full"
        ]
        full_recent_ordinary = [
            i for i in range(recent_boundary, compact_tail_boundary)
            if not protected_flags[i] and self._rolling_compaction_level(rendered[i] or "") == "full"
        ]
        full_recent_protected = [
            i for i in range(recent_boundary, compact_tail_boundary)
            if protected_flags[i] and self._rolling_compaction_level(rendered[i] or "") == "full"
        ]
        for phase in (full_old_ordinary, full_old_protected, full_recent_ordinary, full_recent_protected):
            if apply_transform(phase, self._rolling_compact_turn):
                break

        # Tier 2: compact/full -> minimal semantic ledger. This is what allows
        # recovery after the real server tokenizer/template proves the first estimate
        # too optimistic. Protected turns retain larger excerpts than ordinary turns.
        if not fits():
            minimal_old_ordinary = [i for i in range(compact_tail_boundary) if not protected_flags[i]]
            minimal_old_protected = [i for i in range(compact_tail_boundary) if protected_flags[i]]
            for phase in (minimal_old_ordinary, minimal_old_protected):
                if apply_transform(phase, self._rolling_minimal_turn):
                    break

        # Tier 3: rolling-window eviction. Only completed ordinary historical turns
        # may disappear entirely, oldest first. Session origin is outside this list
        # and pinned; protected constraints/mutations/uncertain turns are never evicted.
        if not fits():
            for index in range(compact_tail_boundary):
                if protected_flags[index] or status_values[index] != "completed" or not rendered[index]:
                    continue
                rendered[index] = None
                changed_indexes.add(index)
                evicted_indexes.add(index)
                candidate = rebuild()
                if fits():
                    break

        after_tokens, after_source = candidate_tokens()
        self._telemetry["context_admission_tokens"] = after_tokens
        self._telemetry["context_admission_source"] = after_source
        if after_tokens > target_input_tokens:
            if after_source == "llama_input_tokens":
                raise VFXContextLimitError(
                    "The current request plus protected AI Director session memory cannot fit alongside the semantic Resolve tool surface. "
                    f"Exact llama-server input is {after_tokens} tokens; the safe prompt budget is {prompt_budget}. "
                    "Increase Context Length, clear/start a new session, or use a smaller request."
                )
            raise VFXContextLimitError(
                "The current request plus protected AI Director session memory cannot fit alongside the semantic Resolve tool surface. Increase Context Length, clear/start a new session, or use a smaller request."
            )

        if changed_indexes:
            protected_compacted = sum(1 for i in changed_indexes if protected_flags[i])
            self._telemetry["context_compactions"] = self._metric_int(self._telemetry.get("context_compactions")) + 1
            self._telemetry["context_compacted_turns"] = self._metric_int(self._telemetry.get("context_compacted_turns")) + len(changed_indexes)
            self._telemetry["context_compaction_before_tokens"] = max(
                self._metric_int(self._telemetry.get("context_compaction_before_tokens")),
                before_tokens,
            )
            self._telemetry["context_compaction_after_tokens"] = after_tokens
            self._emit_progress(
                "context_compaction",
                phase="context_compaction",
                label="Rolling Window compacted older session history",
                policy=CONTEXT_OVERFLOW_ROLLING,
                stage=stage,
                compacted_turns=len(changed_indexes),
                protected_turns=protected_compacted,
                evicted_turns=len(evicted_indexes),
                before_tokens=before_tokens,
                after_tokens=after_tokens,
                target_tokens=target_input_tokens,
                admission_source=after_source,
                round=round_index,
            )
        return candidate

    def _fit_messages_to_context(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[Mapping[str, Any]],
        *,
        aggressive: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Keep all discovered tools available while bounding conversational history.
        Old tool exchanges become an evidence ledger. Raw results remain in
        all_results for runtime observability; only the model-facing history is
        compacted.
        The llama.cpp Qwen template requires the system message to be first.
        Execution memory is therefore merged into that existing first system
        message rather than appended as a second system message.
        """
        prompt_budget = (
            self.context_length
            - self.max_output_tokens
            - DEFAULT_CONTEXT_SAFETY_MARGIN_TOKENS
        )
        if prompt_budget <= 0:
            raise VFXRuntimeError(
                "context_length is too small for the configured output and safety margin."
            )
        tool_tokens = _approx_tokens(tool_definitions)
        available_message_tokens = prompt_budget - tool_tokens
        if available_message_tokens <= 1024:
            raise VFXContextLimitError(
                "The complete Resolve tool inventory leaves insufficient context "
                "for the user request and execution history. Increase context_length."
            )
        full_input_tokens, admission_source = self._admission_input_tokens(
            messages, tool_definitions, exact_preferred=True
        )
        self._telemetry["context_admission_tokens"] = full_input_tokens
        self._telemetry["context_admission_source"] = admission_source
        self._telemetry["context_prompt_budget_tokens"] = prompt_budget
        if full_input_tokens <= prompt_budget:
            return messages
        if len(messages) <= 2:
            if admission_source == "llama_input_tokens":
                raise VFXContextLimitError(
                    "AI Director's fixed execution surface and current request do not fit this configured safe prompt budget. "
                    f"Exact llama-server input is {full_input_tokens} tokens; the safe prompt budget is {prompt_budget}. "
                    "Increase Context Length or reduce Max Output Tokens."
                )
            raise VFXContextLimitError(
                "AI Director session context and current request cannot fit alongside "
                "the semantic Resolve tool surface. Reduce session context or increase context_length."
            )
        prefix = [dict(messages[0]), dict(messages[1])]
        existing_memory = ""
        # Preferred format: execution memory lives inside the single leading
        # system message. Strip it temporarily so it can be rebuilt/extended.
        system_content = prefix[0].get("content")
        if isinstance(system_content, str):
            marker_index = system_content.find(EXECUTION_MEMORY_MARKER)
            if marker_index >= 0:
                existing_memory = system_content[marker_index:].strip()
                prefix[0]["content"] = system_content[:marker_index].rstrip()
        # Backward compatibility for a pre-fix in-memory message sequence.
        if not existing_memory:
            for message in messages[2:]:
                content = message.get("content")
                if (
                    message.get("role") == "system"
                    and isinstance(content, str)
                    and content.startswith(EXECUTION_MEMORY_MARKER)
                ):
                    existing_memory = content
                    break
        blocks = _round_blocks(messages)
        keep_rounds = 0 if aggressive else min(
            DEFAULT_RECENT_ROUNDS_TO_KEEP,
            len(blocks),
        )
        while keep_rounds >= 0:
            old_blocks = blocks[:-keep_rounds] if keep_rounds else blocks
            recent_blocks = blocks[-keep_rounds:] if keep_rounds else []
            memory_text = _execution_memory_message(
                old_blocks,
                existing_memory,
            )
            candidate = [dict(prefix[0]), dict(prefix[1])]
            if memory_text is not None:
                candidate[0]["content"] = (
                    str(candidate[0].get("content", "")).rstrip()
                    + "\n\n"
                    + memory_text
                )
            for block in recent_blocks:
                candidate.extend(block)
            candidate_input_tokens, candidate_source = self._admission_input_tokens(
                candidate, tool_definitions, exact_preferred=True
            )
            self._telemetry["context_admission_tokens"] = candidate_input_tokens
            self._telemetry["context_admission_source"] = candidate_source
            if (
                candidate_input_tokens <= prompt_budget
                if candidate_source == "llama_input_tokens"
                else _approx_tokens(candidate) <= available_message_tokens
            ):
                return candidate
            if keep_rounds == 0:
                break
            keep_rounds -= 1
        # Final fallback: keep task prefix + compact memory only.
        memory_text = _execution_memory_message(
            blocks,
            existing_memory,
        )
        candidate = [dict(prefix[0]), dict(prefix[1])]
        if memory_text is not None:
            candidate[0]["content"] = (
                str(candidate[0].get("content", "")).rstrip()
                + "\n\n"
                + memory_text
            )
        candidate_input_tokens, candidate_source = self._admission_input_tokens(
            candidate, tool_definitions, exact_preferred=True
        )
        self._telemetry["context_admission_tokens"] = candidate_input_tokens
        self._telemetry["context_admission_source"] = candidate_source
        if (
            candidate_input_tokens <= prompt_budget
            if candidate_source == "llama_input_tokens"
            else _approx_tokens(candidate) <= available_message_tokens
        ):
            return candidate
        if candidate_source == "llama_input_tokens":
            raise VFXContextLimitError(
                "Execution history cannot fit alongside the semantic Resolve tool surface. "
                f"Exact llama-server input is {candidate_input_tokens} tokens; safe prompt budget is {prompt_budget}. "
                "Increase Context Length or reduce Max Output Tokens."
            )
        raise VFXContextLimitError(
            "Execution history cannot fit alongside the complete Resolve tool "
            "inventory within the configured context. Increase context_length."
        )

    def _execution_messages(
        self,
        user_input: str,
        tool_count: int,
        session_context: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Build the canonical execution prefix used by both priming and live turns."""
        system_content = (
            f"{self.director_prompt}\n\n"
            "RUNTIME IDENTITY\n\n"
            "Assistant identity: AI Director.\n"
            f"Current model identifier: {self.model}\n"
            "Integration context: DaVinci Resolve.\n"
            "The model identifier above is runtime metadata supplied by "
            "AI Director; do not present it as independent self-inspection.\n\n"
            "EXECUTION ROLE\n\n"
            "You are executing the user's request through the "
            "attached Resolve MCP tools.\n"
            f"The COMPLETE discovered Resolve MCP surface is attached "
            f"to every execution turn ({tool_count} tools). Every "
            "discovered tool remains individually available. The "
            "runtime may compact schema metadata and older conversation "
            "history for context efficiency, but it never removes a "
            "discovered tool from availability.\n"
            "Select the tools required for the user's request directly "
            "from the complete attached MCP surface. Use any necessary "
            "follow-up tools when results establish that more evidence "
            "is required.\n"
            "Treat every MCP result as evidence about Resolve state.\n"
            "Do not claim an operation succeeded unless the result "
            "supports that claim.\n"
            "For current/active/open-state questions, prefer direct "
            "current-state operations and never substitute Media Pool "
            "selection, list order, index lookup, timestamps, or IDs.\n"
            "For mutations, verify the final requested state when the "
            "write result alone does not establish it.\n"
            "Preserve the user's requested scope and do not make "
            "unrelated changes.\n"
            "Keep the final response factual and concise while stating "
            "meaningful uncertainty or inference."
        )
        session_text = (session_context or "").strip()
        user_content = user_input
        if session_text:
            if len(session_text) > MAX_SESSION_CONTEXT_CHARS:
                if self.context_overflow_policy == CONTEXT_OVERFLOW_STOP:
                    prompt_budget_chars = max(1, self._context_configuration()["prompt_budget_tokens"] * int(DEFAULT_TOKEN_ESTIMATE_CHARS))
                    if len(session_text) > prompt_budget_chars:
                        raise VFXContextLimitError(self._stop_at_limit_message())
                else:
                    raise VFXContextLimitError(
                        "AI Director session memory exceeded the absolute semantic rolling source guard. "
                        "Clear/start a new session or reduce retained history."
                    )
            if not session_text.startswith(SESSION_CONTEXT_MARKER):
                raise VFXProtocolError(
                    "AI Director session context is missing its runtime marker."
                )
            user_content = (
                session_text
                + "\n\nCURRENT USER REQUEST\n"
                + user_input
            )
        return [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                # Session context and the current request stay in the final user
                # turn so the expensive static director/tool prefix remains
                # reusable by llama-server prompt caching.
                "content": user_content,
            },
        ]

    def prime_execution_cache(self) -> dict[str, Any]:
        """Evaluate the canonical execution prefix without generating or using MCP.

        llama-server's max_tokens=0 mode evaluates the prompt into its prompt
        cache while producing no model output. This method intentionally uses
        the same messages, model-facing compound tool definitions, and tool-choice
        settings as a live execution turn so the first real user request can reuse the
        static prefix. It never executes a returned tool call because no output
        tokens are generated and no MCP endpoint is invoked here.
        """
        tool_definitions = self._all_tool_definitions()
        tool_count = len(tool_definitions)
        if tool_count == 0:
            raise VFXServerError(
                "No Resolve MCP tools are available for execution-cache priming."
            )

        messages = self._execution_messages(
            "SoR execution cache prime. Do not perform any task.",
            tool_count,
        )
        started = time.monotonic()
        response = self._request(
            "POST",
            self.chat_endpoint,
            json={
                "model": self.model,
                "messages": messages,
                "tools": tool_definitions,
                "tool_choice": "auto",
                "parallel_tool_calls": True,
                "temperature": 0.1,
                "max_tokens": 0,
                "cache_prompt": True,
                "stream": False,
            },
        )
        if not isinstance(response, Mapping):
            raise VFXProtocolError(
                "Execution-cache priming returned a non-object response."
            )

        usage = response.get("usage")
        usage_map = usage if isinstance(usage, Mapping) else {}
        prompt_tokens = self._metric_int(usage_map.get("prompt_tokens"))
        details = usage_map.get("prompt_tokens_details")
        details_map = details if isinstance(details, Mapping) else {}
        cached_tokens = self._metric_int(details_map.get("cached_tokens"))
        return {
            "status": "primed",
            "tool_count": tool_count,
            "prompt_tokens": prompt_tokens,
            "cached_prompt_tokens": cached_tokens,
            "evaluated_prompt_tokens": max(0, prompt_tokens - cached_tokens),
            "elapsed_ms": max(0, int((time.monotonic() - started) * 1000.0)),
        }

    @staticmethod
    def _stop_at_limit_message() -> str:
        return (
            "Context limit reached. This request would exceed the configured safe "
            "context window without truncating session or execution history. "
            "Increase Context Length, clear/start a new session, or switch Context "
            "Overflow to Rolling Window."
        )

    def _stop_at_limit_guard(
        self,
        messages: list[dict[str, Any]],
        tool_definitions: list[Mapping[str, Any]],
        *,
        round_index: Optional[int],
        stage: str,
    ) -> dict[str, Any]:
        body = {"messages": messages, "tools": tool_definitions}
        status = self._projected_context_status(
            body,
            role="execution",
            call_index=self._metric_int(self._telemetry.get("model_calls")) + 1,
            round_index=round_index,
        )
        status["overflow_stage"] = stage
        self._emit_context_status(status)
        if self._metric_int(status.get("projected_prompt_tokens")) > self._metric_int(status.get("prompt_budget_tokens")):
            self._emit_progress(
                "context_limit",
                phase="context_limit",
                label="Context limit reached",
                policy=CONTEXT_OVERFLOW_STOP,
                stage=stage,
                context=status,
            )
            raise VFXContextLimitError(self._stop_at_limit_message())
        return status

    def run_turn(
        self,
        user_input: str,
        *,
        session_context: Optional[str] = None,
        progress_callback: Optional[Callable[[Mapping[str, Any]], None]] = None,
    ) -> VFXTurnResult:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError(
                "VFX user input must be non-empty."
            )
        self._begin_execution(progress_callback)
        self._emit_progress(
            "phase",
            phase="preparing_execution",
            label="Preparing execution",
        )
        try:
            # Attach the semantic compound/default MCP surface to the model.
            # discover_tools() still retains the complete 444-tool inventory for
            # runtime authorization/execution. There is intentionally no second
            # model-based planner pass. This diagnostic tests whether restoring
            # upstream compound semantics fixes tool-selection convergence.
            tool_definitions = self._all_tool_definitions()
            tool_count = len(tool_definitions)
            if tool_count == 0:
                raise VFXServerError(
                    "No Resolve MCP tools are available for execution."
                )
            messages = self._execution_messages(
                user_input,
                tool_count,
                session_context=session_context,
            )
            base_system_content = messages[0]["content"]
            all_calls: list[VFXToolCall] = []
            all_results: list[str] = []
            round_index = 0
            while True:
                self._ensure_execution_budget()
                round_index += 1
                self._emit_progress(
                    "phase",
                    phase="execution",
                    label=f"Model round {round_index}",
                    round=round_index,
                )
                try:
                    if self.context_overflow_policy == CONTEXT_OVERFLOW_STOP:
                        self._stop_at_limit_guard(
                            messages,
                            tool_definitions,
                            round_index=round_index,
                            stage="before_model_call",
                        )
                    else:
                        messages = self._fit_rolling_session_context(
                            messages,
                            tool_definitions,
                            round_index=round_index,
                            stage="before_model_call",
                        )
                        messages = self._fit_messages_to_context(
                            messages,
                            tool_definitions,
                        )
                    response = self._chat_completion_request(
                        {
                            "model": self.model,
                            "messages": messages,
                            "tools": tool_definitions,
                            "tool_choice": "auto",
                            "parallel_tool_calls": True,
                            **self._execution_sampling_parameters(),
                            "max_tokens": self.max_output_tokens,
                        },
                        model_call_role="execution",
                        round_index=round_index,
                    )
                except VFXContextLimitError:
                    if self.context_overflow_policy == CONTEXT_OVERFLOW_STOP:
                        raise
                    recovered = False
                    for attempt in range(DEFAULT_CONTEXT_RECOVERY_ATTEMPTS):
                        try:
                            if attempt == 0:
                                # First recovery keeps the current semantic model-facing surface but
                                # aggressively removes conversational history.
                                messages = self._fit_rolling_session_context(
                                    messages,
                                    tool_definitions,
                                    round_index=round_index,
                                    stage="context_recovery",
                                    aggressive=True,
                                )
                                messages = self._fit_messages_to_context(
                                    messages,
                                    tool_definitions,
                                    aggressive=True,
                                )
                            else:
                                # Second recovery removes nested property prose but
                                # preserves the compound function descriptions/action
                                # catalogs. Never fall back to 444 descriptionless
                                # schemas, which recreates the verified selection defect.
                                available = self.discover_tools()
                                tool_definitions = self._semantic_model_tool_definitions(
                                    property_description_chars=0,
                                )
                                self._model_tool_definitions = tool_definitions
                                self._model_tool_definitions_source = id(available)
                                self._model_tool_definition_mode = (
                                    "compound-advanced-semantic-recovery"
                                )
                                messages = self._fit_rolling_session_context(
                                    messages,
                                    tool_definitions,
                                    round_index=round_index,
                                    stage="semantic_tool_recovery",
                                    aggressive=True,
                                )
                                messages = self._fit_messages_to_context(
                                    messages,
                                    tool_definitions,
                                    aggressive=True,
                                )
                            response = self._chat_completion_request(
                                {
                                    "model": self.model,
                                    "messages": messages,
                                    "tools": tool_definitions,
                                    "tool_choice": "auto",
                                    "parallel_tool_calls": True,
                                    **self._execution_sampling_parameters(),
                                    "max_tokens": self.max_output_tokens,
                                },
                                model_call_role="execution",
                                round_index=round_index,
                            )
                            recovered = True
                            break
                        except VFXContextLimitError:
                            continue
                    if not recovered:
                        if self._last_exact_input_tokens is not None:
                            budget = self._context_configuration()["prompt_budget_tokens"]
                            raise VFXContextLimitError(
                                "VFX context recovery exhausted while preserving the semantic compound + advanced Resolve tool surface. "
                                f"Last exact llama-server input was {self._last_exact_input_tokens} tokens; safe prompt budget is {budget}. "
                                "Increase Context Length or reduce Max Output Tokens."
                            )
                        raise VFXContextLimitError(
                            "VFX context recovery exhausted while preserving the semantic "
                            "compound + advanced Resolve tool surface. Increase context_length."
                        )
                assistant = self._assistant_message(response)
                calls = self._extract_calls(assistant)
                if not calls:
                    content = assistant.get("content")
                    if isinstance(content, str) and content.strip():
                        self._emit_progress(
                            "phase",
                            phase="finalizing",
                            label="Finalizing",
                            round=round_index,
                        )
                        summary = self._telemetry_summary(status="completed")
                        self._emit_progress("complete", summary=summary)
                        return VFXTurnResult(
                            content.strip(),
                            tuple(all_calls),
                            tuple(all_results),
                            round_index,
                            summary,
                        )

                    # Some reasoning-enabled chat templates can legitimately
                    # terminate an assistant generation with reasoning_content
                    # populated but no visible content. Treat that as a
                    # recoverable continuation boundary rather than a protocol
                    # failure. Preserve the assistant message exactly, then ask
                    # the model for its user-facing answer without restarting
                    # completed work or exposing hidden reasoning.
                    reasoning_content = assistant.get("reasoning_content")
                    if (
                        isinstance(reasoning_content, str)
                        and reasoning_content.strip()
                    ):
                        messages.append(dict(assistant))
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Your previous assistant turn completed its "
                                    "reasoning but did not emit a visible final "
                                    "answer. Continue from that reasoning and "
                                    "provide the final user-facing answer now. "
                                    "Do not expose or quote hidden reasoning. "
                                    "Do not restart completed work or repeat "
                                    "completed tool calls unless additional "
                                    "evidence is required."
                                ),
                            }
                        )
                        continue

                    raise VFXProtocolError(
                        "Model returned neither tool calls, a final message, "
                        "nor reasoning content."
                    )
                messages.append(dict(assistant))
                round_results: list[str] = []
                for call_position, call in enumerate(calls, start=1):
                    self._ensure_execution_budget()
                    if self.context_overflow_policy == CONTEXT_OVERFLOW_STOP:
                        self._stop_at_limit_guard(
                            messages,
                            tool_definitions,
                            round_index=round_index,
                            stage=f"before_tool_{call_position}",
                        )
                    self._telemetry["tool_calls"] = self._metric_int(self._telemetry.get("tool_calls")) + 1
                    tool_call_index = self._telemetry["tool_calls"]
                    self._emit_progress(
                        "tool_start",
                        phase="tool",
                        label="Calling Resolve tool",
                        tool_name=call.tool_name,
                        tool_arguments=dict(call.arguments),
                        tool_call_index=tool_call_index,
                        round=round_index,
                        round_position=call_position,
                        round_total=len(calls),
                    )
                    result_text = self._execute_tool(call)
                    result_excerpt = _compact_result_text(
                        result_text,
                        MAX_PROGRESS_RESULT_EXCERPT_CHARS,
                    )
                    self._emit_progress(
                        "tool_complete",
                        phase="tool",
                        tool_name=call.tool_name,
                        tool_arguments=dict(call.arguments),
                        result_excerpt=result_excerpt,
                        tool_call_index=tool_call_index,
                        round=round_index,
                        round_position=call_position,
                        round_total=len(calls),
                        summary=self._telemetry_summary(),
                    )
                    all_calls.append(call)
                    all_results.append(result_text)
                    round_results.append(result_text)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "content": result_text,
                        }
                    )
                recovery_notice = self._record_round_progress(
                    calls,
                    round_results,
                )
                # Preserve compact execution memory inside the single leading
                # system message while adding/removing the transient recovery notice.
                execution_memory = ""
                current_system_content = messages[0].get("content")
                if isinstance(current_system_content, str):
                    marker_index = current_system_content.find(EXECUTION_MEMORY_MARKER)
                    if marker_index >= 0:
                        execution_memory = current_system_content[marker_index:].strip()
                if recovery_notice:
                    system_content = (
                        base_system_content
                        + "\n\nRUNTIME EXECUTION NOTICE\n"
                        + recovery_notice
                    )
                else:
                    system_content = base_system_content
                if execution_memory:
                    system_content = system_content.rstrip() + "\n\n" + execution_memory
                messages[0]["content"] = system_content
        finally:
            self._clear_execution()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "AI Director / DaVinci Resolve runtime"
        )
    )
    parser.add_argument(
        "request",
        nargs="*",
        help="Natural-language VFX/DaVinci Resolve request.",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
    )
    parser.add_argument(
        "--prompt-path",
        default=None,
        help=(
            "Optional path to VFXDirector.txt. "
            "Defaults to prompts/VFXDirector.txt beside this file."
        ),
    )
    args = parser.parse_args()
    runtime = VFXRuntime(
        prompt_path=args.prompt_path,
    )
    try:
        if args.list_tools:
            for name in sorted(
                runtime.discover_tools()
            ):
                print(name)
            return 0
        request = (
            " ".join(args.request).strip()
            or input("VFX > ").strip()
        )
        if not request:
            print("[VFX ERROR] Request is empty.")
            return 2
        result = runtime.run_turn(request)
        for call in result.tool_calls:
            print(
                f"[TOOL] {call.tool_name} - completed"
            )
        print(
            f"\nAI Director > {result.final_message}"
        )
        return 0
    except VFXRuntimeError as exc:
        print(f"[VFX ERROR] {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[VFX] Session terminated by user.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
