"""Interactive console interface for SyntecBot."""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
from pathlib import Path
from typing import Callable, Optional, Sequence

from .engine import ChatBot
from .logger import ConversationLogger

BANNER = """\
==============================================================
  SyntecBot - Simple Rule-Based Chatbot   (Syntecxhub AI Internship)
==============================================================
  Ask me about Artificial Intelligence or just say hello.
  Type 'help' for ideas, 'topics' for my subjects, 'exit' to quit.
  Commands: /help /topics /history /save [file] /clear /exit
--------------------------------------------------------------"""


def _style(text: str, code: str, use_color: bool) -> str:
    return f"\033[{code}m{text}\033[0m" if use_color else text


def _wrap(text: str, width: int = 88) -> str:
    out = []
    for line in text.split("\n"):
        indent = len(line) - len(line.lstrip())
        out.append(textwrap.fill(line, width=width, subsequent_indent=" " * (indent + 2)) if line.strip() else "")
    return "\n".join(out)


def run_chat(bot: ChatBot, logger: ConversationLogger,
             input_fn: Callable[[str], str] = input,
             print_fn: Callable[..., None] = print,
             use_color: bool = False) -> None:
    """Main read-eval-print loop. Input/output functions are injectable for testing."""
    prompt = _style("You> ", "36", use_color)
    label = _style(f"{bot.bot_name}>", "32", use_color)

    def say(reply_text: str) -> None:
        print_fn(f"{label} {_wrap(reply_text)}")

    print_fn(BANNER)
    while True:
        try:
            message = input_fn(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print_fn()
            say("Goodbye! (session saved)")
            break
        if not message:
            continue

        if message.startswith("/"):
            command, _, arg = message[1:].partition(" ")
            command = command.lower()
            if command in ("exit", "quit"):
                say("Goodbye! Thanks for chatting.")
                break
            elif command == "help":
                say(bot.respond("help").text)
            elif command == "topics":
                say(bot.respond("topics").text)
            elif command == "history":
                print_fn(logger.format_history())
            elif command == "save":
                path = logger.export_text(Path(arg.strip()) if arg.strip() else None)
                say(f"Conversation saved to {path}")
            elif command == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                print_fn(BANNER)
            else:
                say(f"Unknown command '/{command}'. Type /help to see the commands.")
            continue

        logger.add("user", message)
        reply = bot.respond(message)
        logger.add("bot", reply.text, intent=reply.intent, confidence=reply.confidence)
        say(reply.text)
        if reply.exit:
            break

    if logger.enabled and logger.entries:
        print_fn(f"(Conversation log: {logger.path})")
    elif logger.error:
        print_fn(f"(Could not write log file: {logger.error})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatbot", description="SyntecBot - a simple rule-based chatbot")
    parser.add_argument("--no-log", action="store_true", help="do not write the conversation log file")
    parser.add_argument("--log-dir", type=Path, default=None, help="folder for conversation logs (default: ./logs)")
    parser.add_argument("--history", action="store_true", help="print the most recent saved conversation and exit")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    for stream in (sys.stdout, sys.stdin):  # avoid UnicodeEncodeError on Windows consoles
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    if args.history:
        latest = ConversationLogger.latest_session(args.log_dir)
        print(ConversationLogger.read_session(latest) if latest else "No saved conversations yet.")
        return 0

    use_color = sys.stdout.isatty() and "NO_COLOR" not in os.environ
    if use_color and os.name == "nt":
        os.system("")  # enable ANSI escape codes on Windows 10+
    bot = ChatBot()
    logger = ConversationLogger(log_dir=args.log_dir, enabled=not args.no_log)
    run_chat(bot, logger, use_color=use_color)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
