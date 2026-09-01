"""Copy all objects from one Supabase Storage bucket to a local backup folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def api_json(url: str, key: str, *, method: str = "GET", body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def list_prefix(base: str, bucket: str, key: str, prefix: str) -> list[dict]:
    result: list[dict] = []
    offset = 0
    while True:
        items = api_json(
            f"{base}/storage/v1/object/list/{quote(bucket, safe='')}",
            key,
            method="POST",
            body={"prefix": prefix, "limit": 1000, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
        )
        result.extend(items)
        if len(items) < 1000:
            return result
        offset += len(items)


def walk_objects(base: str, bucket: str, key: str, prefix: str = ""):
    for item in list_prefix(base, bucket, key, prefix):
        name = str(item.get("name", ""))
        if not name:
            continue
        path = f"{prefix.rstrip('/')}/{name}".lstrip('/')
        if item.get("id") is None and item.get("metadata") is None:
            yield from walk_objects(base, bucket, key, path)
        else:
            yield path


def download_object(base: str, bucket: str, key: str, object_path: str, destination: Path) -> str:
    url = f"{base}/storage/v1/object/authenticated/{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
    request = Request(url, headers={"Authorization": f"Bearer {key}", "apikey": key})
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    bucket = os.environ["SUPABASE_STORAGE_BUCKET"]
    output = args.output.resolve()
    manifest = []
    for object_path in walk_objects(base, bucket, key):
        target = (output / object_path).resolve()
        if output not in target.parents:
            raise ValueError(f"unsafe Storage path: {object_path}")
        checksum = download_object(base, bucket, key, object_path, target)
        manifest.append({"path": object_path, "sha256": checksum, "bytes": target.stat().st_size})
        print(object_path)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, HTTPError, URLError) as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
