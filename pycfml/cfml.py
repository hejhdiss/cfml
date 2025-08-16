#!/usr/bin/env python3

# Copyright (c) 2025 Muhammed Shafin P (hejhdiss)
# All rights reserved.
# Licensed under Argophore License, Version 1.0
# See LICENSE file for details.

import re
from typing import List, Dict, Optional


class FormatError(ValueError):
    """Raised when input text does not match the required format."""

class CFMLError(Exception):
    """Base error for all CFML operations."""

class ParseError(CFMLError):
    """Raised when parsing CFML text fails."""

class ValidationError(CFMLError):
    """Raised when operations on data are invalid."""

class FileError(CFMLError):
    """Raised when file operations fail."""

class CustomFormatDB:
    HEADER_RE = re.compile(r"^#\$\* date -\* (?P<date>.*?) \*-\s#\$\*$")
    MESSAGE_RE = re.compile(
        r"^@# (?P<time>\d{2}:\d{2}:\d{2}) #@ "
        r"\$# (?P<receiver>.+?) #\$ "
        r"\*# (?P<sender>.+?) #\* "
        r"content -\*&\^# (?P<content>.+?) #\^&\*-$"
    )
    END_RE = re.compile(r"^\*\$# end \*\$#$")

    def __init__(self):
        self.blocks: List[Dict] = []  # [{date: str, messages: [dict,...]}]

    # ------------------ CORE PARSER ------------------ #
    def load(self, text: str):
        self.blocks.clear()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        current_date = None
        current_messages = []

        for line in lines:
            header = self.HEADER_RE.match(line)
            if header:
                if current_date is not None:
                    raise FormatError("New date block started before 'end' marker.")
                current_date = header.group("date")
                current_messages = []
                continue

            msg = self.MESSAGE_RE.match(line)
            if msg:
                if current_date is None:
                    raise FormatError("Message found before date header.")
                for key in ("time", "receiver", "sender", "content"):
                    if not msg.group(key):
                        raise FormatError(f"Missing field: {key}")
                current_messages.append({
                    "time": msg.group("time"),
                    "receiver": msg.group("receiver"),
                    "sender": msg.group("sender"),
                    "content": msg.group("content"),
                })
                continue

            if self.END_RE.match(line):
                if current_date is None:
                    raise FormatError("End marker found without starting date.")
                self.blocks.append({"date": current_date, "messages": current_messages})
                current_date = None
                current_messages = []
                continue

            raise FormatError(f"Invalid line format: {line}")

        if current_date is not None:
            raise FormatError("Missing 'end' marker for last date block.")

    def dumps(self) -> str:
        output = []
        for block in self.blocks:
            output.append(f"#$* date -* {block['date']} *- #$*")
            for msg in block["messages"]:
                output.append(
                    f"@# {msg['time']} #@ "
                    f"$# {msg['receiver']} #$ "
                    f"*# {msg['sender']} #* "
                    f"content -*&^# {msg['content']} #^&*-"
                )
            output.append("*$# end *$#")
        return "\n".join(output)

    # ------------------ DATA MANAGEMENT ------------------ #
    def add_message(self, date: str, time: str, receiver: str, sender: str, content: str):
        for field, value in {"date": date, "time": time,
                             "receiver": receiver, "sender": sender, "content": content}.items():
            if not value:
                raise FormatError(f"Missing required field: {field}")

        for block in self.blocks:
            if block["date"] == date:
                block["messages"].append({
                    "time": time, "receiver": receiver,
                    "sender": sender, "content": content
                })
                return

        self.blocks.append({
            "date": date,
            "messages": [{
                "time": time, "receiver": receiver,
                "sender": sender, "content": content
            }]
        })

    def delete_date(self, date: str):
        """Delete entire date block"""
        self.blocks = [b for b in self.blocks if b["date"] != date]

    def delete_message(self, date: str, index: int):
        """Delete specific message by index under a date"""
        for block in self.blocks:
            if block["date"] == date:
                if 0 <= index < len(block["messages"]):
                    block["messages"].pop(index)
                    return
                else:
                    raise FormatError(f"Invalid message index: {index}")
        raise FormatError(f"No such date block: {date}")

    def edit_message(self, date: str, index: int, updates: Dict[str, str]):
        """Edit fields in a message (only time/receiver/sender/content allowed)."""
        for block in self.blocks:
            if block["date"] == date:
                if 0 <= index < len(block["messages"]):
                    msg = block["messages"][index]
                    for key in updates:
                        if key not in ("time", "receiver", "sender", "content"):
                            raise FormatError(f"Invalid field for edit: {key}")
                        if not updates[key]:
                            raise FormatError(f"Empty value not allowed for {key}")
                        msg[key] = updates[key]
                    return
                else:
                    raise FormatError(f"Invalid message index: {index}")
        raise FormatError(f"No such date block: {date}")

    def list_dates(self) -> List[str]:
        return [b["date"] for b in self.blocks]

    def list_messages(self, date: str) -> List[Dict]:
        for block in self.blocks:
            if block["date"] == date:
                return block["messages"]
        raise FormatError(f"No such date block: {date}")

    def search_messages(self, sender: Optional[str] = None,
                        receiver: Optional[str] = None,
                        text: Optional[str] = None) -> List[Dict]:
        results = []
        for block in self.blocks:
            for msg in block["messages"]:
                if sender and msg["sender"] != sender:
                    continue
                if receiver and msg["receiver"] != receiver:
                    continue
                if text and text not in msg["content"]:
                    continue
                results.append({"date": block["date"], **msg})
        return results

    # ------------------ FILE HELPERS ------------------ #
    @classmethod
    def from_file(cls, filename: str):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            raise FileError(f"Could not read file '{filename}': {e}") from e
        db = cls()
        db.load(text)  # may raise ParseError
        return db

    def to_file(self, filename: str):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.dumps())
        except OSError as e:
            raise FileError(f"Could not write to file '{filename}': {e}") from e
    
