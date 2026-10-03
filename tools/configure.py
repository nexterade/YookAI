"""Interactive startup configuration for YookAI."""
from __future__ import annotations

import getpass
import os
import sys
import threading
import time
from typing import Any

from core.config import save_config
from core.latency import get_result, put_result
from providers.openrouter import OpenRouterProvider
from providers.ollama import OllamaProvider
from providers.openai import OpenAIProvider
from providers.anthropic import AnthropicProvider
from providers.gemini import GeminiProvider

PROVIDER_LABELS={"openrouter":"OpenRouter","openai":"OpenAI","anthropic":"Anthropic","gemini":"Google Gemini","ollama":"Ollama API"}
PROVIDER_DEFAULT_MODELS = {"openrouter":"qwen/qwen3.8-27b:free", "gemini":"gemini-2.5-flash", "openai":"gpt-4o-mini", "anthropic":"claude-3-5-haiku-20241022", "ollama":"llama3.2"}

class _Spinner:
    """Animated terminal status that never blocks the work it represents."""
    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, message: str, interval: float = 0.1) -> None:
        self.message = message
        self.interval = interval
        self.enabled = (bool(getattr(sys.stdout, "isatty", lambda: False)())
                        and os.environ.get("TERM", "") != "dumb")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        if self.enabled:
            self._thread = threading.Thread(target=self._animate, name="yookai-cli-spinner", daemon=True)
            self._thread.start()
        else:
            print(self.message, flush=True)
        return self

    def _animate(self) -> None:
        index = 0
        while not self._stop.is_set():
            frame = self.FRAMES[index % len(self.FRAMES)]
            sys.stdout.write(f"\r\033[2K{frame} {self.message}")
            sys.stdout.flush()
            index += 1
            self._stop.wait(self.interval)

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=max(1.0, self.interval * 3))
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
        return False


class _Style:
    """Small ANSI palette that safely degrades on non-interactive terminals."""
    enabled = bool(getattr(sys.stdout, "isatty", lambda: False)()) and not bool(__import__("os").environ.get("NO_COLOR"))
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    CYAN = "\033[36m"; BLUE = "\033[34m"; GREEN = "\033[32m"
    YELLOW = "\033[33m"; MAGENTA = "\033[35m"; RED = "\033[31m"

    @classmethod
    def paint(cls, value: str, color: str) -> str:
        return f"{color}{value}{cls.RESET}" if cls.enabled else value


def _banner() -> None:
    title = _Style.paint("✦ YookAI", _Style.CYAN + _Style.BOLD)
    version = _Style.paint("v0.3.9", _Style.MAGENTA)
    print(f"\n{title}  {version}  {_Style.paint('AI CONTROL CENTER', _Style.DIM)}")
    print(_Style.paint("Configure your assistant before the server starts", _Style.DIM))


def _yes_no(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "1", "true"}


PROVIDER_GUIDES = {
    "openrouter": (
        "OpenRouter [GRATIS*] — tersedia model free dan model berbayar.",
        "Catatan: pilih model bertanda :free untuk free tier; ketersediaan, rate limit, dan kuota dapat berubah.",
        "1. Buka https://openrouter.ai/ dan buat akun / masuk.",
        "2. Buka https://openrouter.ai/keys lalu pilih Create API Key.",
        "3. Salin key dan masukkan di Credentials / URL. Jangan bagikan key.",
        "4. Pilih model dari https://openrouter.ai/models (filter Free bila perlu).",
        "Base URL: https://openrouter.ai/api/v1",
    ),
    "openai": (
        "[BAYAR] OpenAI API — berbayar sesuai penggunaan; ChatGPT Plus tidak termasuk kredit API.",
        "1. Masuk atau daftar di https://platform.openai.com/.",
        "2. Buka https://platform.openai.com/api-keys, buat secret key, lalu salin.",
        "3. Pastikan billing / project API sudah disiapkan di dashboard OpenAI.",
        "4. Masukkan key di Credentials / URL dan pilih model yang tersedia untuk project.",
        "Base URL: https://api.openai.com/v1",
    ),
    "anthropic": (
        "[BAYAR] Anthropic API — akses Claude melalui Console; umumnya memerlukan billing / credits.",
        "1. Masuk atau daftar di https://console.anthropic.com/.",
        "2. Buka bagian API Keys, buat key, lalu salin saat ditampilkan.",
        "3. Siapkan billing / credits bila diminta, lalu masukkan key di konfigurasi.",
        "4. Gunakan ID model Claude yang tersedia untuk akun Anda.",
        "Base URL: https://api.anthropic.com",
    ),
    "gemini": (
        "Google Gemini [GRATIS*] — beberapa model memiliki free tier dengan batas penggunaan.",
        "Catatan: penggunaan di luar kuota atau model tertentu dapat memerlukan billing.",
        "1. Buka https://aistudio.google.com/app/apikey dan masuk dengan akun Google.",
        "2. Pilih Create API key, tentukan project jika diminta, lalu salin key.",
        "3. Masukkan key di Credentials / URL dan pilih model Gemini yang tersedia.",
        "4. Periksa batas penggunaan dan ketentuan API di Google AI Studio.",
        "Base URL: https://generativelanguage.googleapis.com/v1beta",
    ),
    "ollama": (
        "Ollama API [SELF-HOSTED] — YookAI terhubung ke server Ollama melalui HTTP API.",
        "1. Jalankan Ollama di PC/laptop/server dan unduh model: ollama pull llama3.2.",
        "2. Pastikan server bisa dijangkau dari perangkat YookAI; untuk Termux gunakan IP LAN server.",
        "3. Contoh URL: http://192.168.1.10:11434 (localhost hanya jika Ollama berjalan di HP yang sama).",
        "4. Pilih menu Model untuk memuat daftar model yang sudah tersedia di server.",
        "Catatan: API Ollama umumnya tanpa API key. Jangan ekspos port ke internet tanpa autentikasi/proteksi.",
    ),
}

def _show_provider_guide(name: str) -> None:
    guide = PROVIDER_GUIDES.get(name)
    if not guide:
        return
    print("\nQuick setup guide")
    for line in guide:
        print(f"  {line}")

def _provider_menu(config: dict[str, Any]) -> None:
    provider=config.setdefault("provider", {})
    names=[("openrouter","OpenRouter [GRATIS*]"),("ollama","Ollama API [SELF-HOSTED]"),("gemini","Google Gemini [GRATIS*]"),("openai","OpenAI [BAYAR]"),("anthropic","Anthropic [BAYAR]")]
    current=provider.get("default","openrouter")
    print("\nProvider")
    for i,(name,label) in enumerate(names,1): print(f"  {i}) {label}")
    choice=input(f"Select [{next((i for i,(n,_) in enumerate(names,1) if n==current),1)}]: ").strip()
    if choice.isdigit() and 1<=int(choice)<=len(names):
        old_name = current
        new_name = names[int(choice)-1][0]
        chat = config.setdefault("chat", {})
        model_map = chat.setdefault("provider_models", {})
        if chat.get("default_model") and old_name:
            model_map[old_name] = chat["default_model"]
        provider["default"] = new_name
        defaults = PROVIDER_DEFAULT_MODELS
        saved_model = model_map.get(new_name, "")
        compatible = {
            "gemini": lambda model: model.startswith("gemini-"),
            "openai": lambda model: model.startswith(("gpt-", "o1", "o3", "o4", "chatgpt-")),
            "anthropic": lambda model: model.startswith("claude-"),
            "ollama": lambda model: bool(model) and "/" not in model,
            "openrouter": lambda model: bool(model),
        }
        if saved_model and not compatible.get(new_name, lambda model: True)(saved_model):
            saved_model = ""
        chat["default_model"] = saved_model or defaults.get(new_name, "")
        chat["model_strategy"] = "manual"
        _show_provider_guide(new_name)


def _credentials_menu(config: dict[str, Any]) -> None:
    name=config.setdefault("provider",{}).get("default","openrouter")
    settings=config["provider"].setdefault(name,{})
    label=PROVIDER_LABELS.get(name,name) if 'PROVIDER_LABELS' in globals() else name.title()
    print(f"\n{label} configuration")
    if name != "ollama":
        current=settings.get("api_key","")
        masked=(current[:7]+"…"+current[-4:]) if current else "not configured"
        print(f"API key: {masked}")
        value=getpass.getpass("New API key (Enter keeps current): ").strip()
        if value: settings["api_key"]=value
    else:
        print("API key tidak diperlukan. Masukkan URL server Ollama yang bisa dijangkau dari YookAI.")
    default_url=settings.get("base_url") or ("http://127.0.0.1:11434" if name == "ollama" else "")
    value=input(f"Base URL [{default_url}]: ").strip()
    settings["base_url"] = value.rstrip("/") if value else default_url


def _benchmark(config: dict[str, Any], force: bool = False) -> dict[str, Any] | None:
    settings = config.get("provider", {}).get("openrouter", {})
    key = settings.get("api_key", "")
    if not key:
        print("\nCannot benchmark: OpenRouter API key is not configured.")
        return None
    base_url = settings.get("base_url", "https://openrouter.ai/api/v1")
    if not force:
        cached = get_result("openrouter", base_url)
        if cached:
            best = cached.get("best_model")
            print(f"\nUsing latency cache: {best} ({cached.get('best_ttft_ms')} ms TTFT)")
            config.setdefault("chat", {})["default_model"] = best
            return cached
    provider = OpenRouterProvider(key, base_url)
    try:
        with _Spinner("Checking free OpenRouter models (streaming probes)..."):
            models = provider.list_models()
            results = provider.benchmark_models(models, max_candidates=5, timeout=(4, 8))
    except Exception as exc:
        print(f"Benchmark failed: {exc}")
        return None
    valid = [r for r in results if r.get("ttft_ms") is not None]
    for result in results:
        if result.get("ttft_ms") is not None:
            print(f"  {result['name']}: {result['ttft_ms']} ms")
        else:
            print(f"  {result['name']}: failed ({result.get('error', 'unknown')})")
    if not valid:
        print("No free model completed the latency probe; keeping the current model.")
        return {"results": results}
    best = valid[0]
    config.setdefault("chat", {})["default_model"] = best["id"]
    config.setdefault("chat", {})["model_strategy"] = "latency-best-free"
    result = {"best_model": best["id"], "best_ttft_ms": best["ttft_ms"], "results": results}
    put_result("openrouter", base_url, result)
    print(f"Selected default: {best['name']} ({best['ttft_ms']} ms TTFT)")
    return result


def _model_menu(config: dict[str, Any]) -> None:
    provider_name = config.setdefault("provider", {}).get("default", "openrouter")
    chat = config.setdefault("chat", {})
    if provider_name == "ollama":
        settings = config["provider"].setdefault("ollama", {})
        base_url = settings.get("base_url") or "http://127.0.0.1:11434"
        settings["base_url"] = base_url.rstrip("/")
        print(f"\nOllama models from {settings['base_url']}")
        try:
            models = OllamaProvider(base_url=settings["base_url"]).list_models()
        except Exception as exc:
            print(f"Could not load server models: {exc}")
            models = []
        if models:
            for i, model in enumerate(models, 1):
                print(f"  {i}) {model['id']}")
            print("  M) Enter model ID manually")
            choice = input(f"Select [{next((i for i,m in enumerate(models,1) if m['id']==chat.get('default_model')),1)}]: ").strip()
            if choice.upper() == "M":
                model_id = input(f"Model ID [{chat.get('default_model','llama3.2')}]: ").strip()
                if model_id: chat["default_model"] = model_id
            elif choice.isdigit() and 1 <= int(choice) <= len(models):
                chat["default_model"] = models[int(choice)-1]["id"]
            elif not choice:
                chat["default_model"] = next((m["id"] for m in models if m["id"] == chat.get("default_model")), models[0]["id"])
        else:
            print("Pastikan URL server benar dan model sudah diunduh (ollama pull <model>).")
            model_id = input(f"Model ID [{chat.get('default_model','llama3.2')}]: ").strip()
            if model_id: chat["default_model"] = model_id
        chat["model_strategy"] = "manual"
        chat.setdefault("provider_models", {})["ollama"] = chat.get("default_model", "llama3.2")
        return
    print("\nModel strategy")
    print("  1) Auto — choose a model available from the active provider")
    print("  2) Keep current provider model")
    print("  3) Enter model ID manually")
    choice = input("Select [1]: ").strip() or "1"
    chat = config.setdefault("chat", {})
    if choice == "1":
        if provider_name == "openrouter":
            chat["model_strategy"] = "latency-best-free"
            _benchmark(config)
        else:
            settings = config.get("provider", {}).get(provider_name, {})
            provider_types = {
                "gemini": GeminiProvider, "openai": OpenAIProvider,
                "anthropic": AnthropicProvider,
            }
            model_list = []
            if provider_name in provider_types and settings.get("api_key"):
                try:
                    cls = provider_types[provider_name]
                    kwargs = {"api_key": settings.get("api_key", "")}
                    if settings.get("base_url"):
                        kwargs["base_url"] = settings["base_url"]
                    models = cls(**kwargs).list_models()
                    model_list = [m.get("id") for m in models if m.get("id")]
                except Exception as exc:
                    print(f"Could not load {PROVIDER_LABELS.get(provider_name, provider_name)} models: {exc}")
            preferred = {
                "gemini": ("gemini-2.5-flash", "gemini-2.0-flash"),
                "openai": ("gpt-4o-mini", "gpt-4.1-mini"),
                "anthropic": ("claude-3-5-haiku-20241022", "claude-3-haiku-20240307"),
            }.get(provider_name, ())
            selected = next((m for candidate in preferred for m in model_list if m == candidate), None)
            selected = selected or (model_list[0] if model_list else PROVIDER_DEFAULT_MODELS.get(provider_name, ""))
            if selected:
                chat["default_model"] = selected
                chat.setdefault("provider_models", {})[provider_name] = selected
                chat["model_strategy"] = "provider-auto" if model_list else "manual"
                print(f"Selected {PROVIDER_LABELS.get(provider_name, provider_name)} model: {selected}")
            else:
                print("No compatible model found; enter a model ID manually after configuring credentials.")
    elif choice == "2":
        saved = chat.get("provider_models", {}).get(provider_name)
        if saved:
            chat["default_model"] = saved
        chat["model_strategy"] = "manual"
    elif choice == "3":
        model = input(f"Model ID [{chat.get('default_model', '')}]: ").strip()
        if model:
            chat["default_model"] = model
            chat.setdefault("provider_models", {})[provider_name] = model
        chat["model_strategy"] = "manual"


def _memory_menu(config: dict[str, Any]) -> None:
    memory = config.setdefault("memory", {})
    current = memory.get("mode", "default")
    print(f"\nMemory mode: {current}")
    print("  1) Default memory — shared across chats")
    print("  2) Project-only memory — isolated to this project")
    choice = input("Select [current]: ").strip()
    if choice == "1": memory["mode"] = "default"
    elif choice == "2": memory["mode"] = "project-only"


def _server_menu(config: dict[str, Any]) -> None:
    server = config.setdefault("server", {})
    host = input(f"Host [{server.get('host', '127.0.0.1')}]: ").strip()
    port = input(f"Port [{server.get('port', 8000)}]: ").strip()
    if host: server["host"] = host
    if port:
        try: server["port"] = int(port)
        except ValueError: print("Invalid port; keeping current value.")


def _theme_menu(config: dict[str, Any]) -> None:
    ui = config.setdefault("ui", {})
    value = input(f"Theme dark/light [{ui.get('theme', 'dark')}]: ").strip().lower()
    if value in {"dark", "light"}: ui["theme"] = value


def interactive_config(config: dict[str, Any], *, force: bool = False) -> dict[str, Any] | None:
    """Run the pre-listen setup menu. Returns None when the user cancels."""
    if not sys.stdin.isatty() and not force:
        return config
    _banner()
    print(_Style.paint("\nSTARTUP CONFIGURATION", _Style.BLUE + _Style.BOLD))
    print(_Style.paint("Changes are saved before the HTTP server starts.\n", _Style.DIM))
    # Migrate the old hard-coded DeepSeek R1 default to the new automatic
    # strategy. Existing users keep their config, but future starts select the
    # fastest free model measured from this device.
    chat_config = config.setdefault("chat", {})
    if chat_config.get("default_model") == "deepseek/deepseek-r1" and "model_strategy" not in chat_config:
        chat_config["model_strategy"] = "latency-best-free"

    # Auto mode is intentionally benchmarked once per cache window so the
    # configured default tracks the user's current OpenRouter routing/latency
    # rather than being hard-coded to a particular model.
    if (config.get("provider", {}).get("default", "openrouter") == "openrouter"
            and config.get("chat", {}).get("model_strategy") == "latency-best-free"
            and config.get("provider", {}).get("openrouter", {}).get("api_key")):
        base_url = config.get("provider", {}).get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
        cached = get_result("openrouter", base_url)
        if cached and cached.get("best_model"):
            config.setdefault("chat", {})["default_model"] = cached["best_model"]
            print(f"Latency cache: {cached['best_model']} ({cached.get('best_ttft_ms')} ms TTFT)")
        else:
            _benchmark(config)
    while True:
        provider_name=config.get("provider",{}).get("default","openrouter")
        provider=config.get("provider",{}).get(provider_name,{})
        chat=config.get("chat",{}); memory=config.get("memory",{}); server=config.get("server",{})
        key_state="URL required / no API key" if provider_name=="ollama" else ("configured" if provider.get("api_key") else "NOT configured")
        print(_Style.paint("─"*62, _Style.DIM))
        rows = [
            ("1", "Provider", PROVIDER_LABELS.get(provider_name,provider_name)),
            ("2", "Credentials / URL", f"{key_state} / {provider.get('base_url') or ('http://127.0.0.1:11434' if provider_name == 'ollama' else '')}"),
            ("3", "Model", f"{chat.get('default_model','none')} ({chat.get('model_strategy','manual')})"),
            ("4", "Memory", memory.get('mode','default')),
            ("5", "Server", f"{server.get('host','127.0.0.1')}:{server.get('port',8000)}"),
            ("6", "Theme", config.get('ui',{}).get('theme','dark')),
        ]
        for number, label, value in rows:
            print(f"{_Style.paint('['+number+']', _Style.CYAN)} {label:<19}: {_Style.paint(str(value), _Style.GREEN)}")
        print(_Style.paint("[7]", _Style.CYAN) + " Benchmark latency  : OpenRouter free models")
        print(_Style.paint("[S]", _Style.GREEN + _Style.BOLD) + " Save & start server")
        print(_Style.paint("[Q]", _Style.RED + _Style.BOLD) + " Quit")
        choice=input(_Style.paint("\nChoose an option: ", _Style.YELLOW + _Style.BOLD)).strip().lower()
        if choice=="1": _provider_menu(config)
        elif choice=="2": _credentials_menu(config)
        elif choice=="3": _model_menu(config)
        elif choice=="4": _memory_menu(config)
        elif choice=="5": _server_menu(config)
        elif choice=="6": _theme_menu(config)
        elif choice=="7": _benchmark(config,force=True)
        elif choice=="s":
            if provider_name!="ollama" and not provider.get("api_key"):
                print(f"Warning: {PROVIDER_LABELS.get(provider_name,provider_name)} API key is not configured; chat requests may fail until it is set.")
            save_config(config); return config
        elif choice=="q": return None
        else: print("Unknown option.")
