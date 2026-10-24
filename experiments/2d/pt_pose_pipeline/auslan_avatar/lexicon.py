"""
Word -> .pt file resolution.

A lexicon is just a directory of motion files named after the sign:

    signs/HELLO.pt
    signs/POSSUM.pt

An optional signs/lexicon.json can add aliases and pick a clip inside a
multi-clip file:

    {
      "entries": {
        "HELLO": {"file": "HELLO.pt", "clip": "video_1_0"},
        "HI":    {"alias": "HELLO"}
      }
    }
"""

import json
import os
from dataclasses import dataclass


@dataclass
class Entry:
    word: str
    path: str
    clip: str = None


class MissingSignError(KeyError):
    def __init__(self, word, available):
        self.word = word
        self.available = available
        preview = ", ".join(sorted(available)[:12])
        super().__init__(
            f"no motion file for {word!r}. Known signs: {preview}"
            + (" ..." if len(available) > 12 else "")
        )


class Lexicon:
    def __init__(self, root, manifest_name="lexicon.json"):
        self.root = root
        self._entries = {}
        self._aliases = {}
        self._load(manifest_name)

    def _load(self, manifest_name):
        if not os.path.isdir(self.root):
            raise FileNotFoundError(f"lexicon directory not found: {self.root}")

        for name in sorted(os.listdir(self.root)):
            if not name.lower().endswith(".pt"):
                continue
            word = os.path.splitext(name)[0]
            self._entries[word.upper()] = Entry(
                word=word.upper(),
                path=os.path.join(self.root, name),
            )

        manifest = os.path.join(self.root, manifest_name)
        if os.path.exists(manifest):
            with open(manifest) as fh:
                spec = json.load(fh)
            for word, cfg in (spec.get("entries") or {}).items():
                key = word.upper()
                if "alias" in cfg:
                    self._aliases[key] = cfg["alias"].upper()
                    continue
                self._entries[key] = Entry(
                    word=key,
                    path=os.path.join(self.root, cfg["file"]),
                    clip=cfg.get("clip"),
                )

    @property
    def words(self):
        return set(self._entries) | set(self._aliases)

    def __contains__(self, word):
        return self.resolve_name(word) is not None

    def resolve_name(self, word):
        key = str(word).strip().upper()
        seen = set()
        while key in self._aliases and key not in seen:
            seen.add(key)
            key = self._aliases[key]
        return key if key in self._entries else None

    def get(self, word):
        key = self.resolve_name(word)
        if key is None:
            raise MissingSignError(word, self.words)
        return self._entries[key]

    def resolve_all(self, words, on_missing="error"):
        """
        Resolve a list of glosses.

        on_missing: "error" raises, "skip" drops the word and reports it.
        Returns (entries, missing).
        """
        entries, missing = [], []
        for word in words:
            key = self.resolve_name(word)
            if key is None:
                if on_missing == "error":
                    raise MissingSignError(word, self.words)
                missing.append(word)
                continue
            entries.append((str(word).strip().upper(), self._entries[key]))
        return entries, missing
