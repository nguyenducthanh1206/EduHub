from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Run: pip install -r requirements.txt")
    raise

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
INDEX_FILE = "metadata_index.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def validate_image(path: Path) -> tuple[int, int]:
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            width, height = im.size
    except Exception as exc:
        raise ValueError(f"Invalid or unreadable image: {path}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {width}x{height}")
    return int(width), int(height)


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def safe_json_dump(data: dict[str, Any], output: Path) -> None:
    tmp = output.with_suffix(output.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(output)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def update_index(metadata: dict[str, Any], index_path: Path) -> None:
    if index_path.exists():
        try:
            index = load_json(index_path)
        except Exception:
            index = {"items": []}
    else:
        index = {"items": []}

    items = index.get("items", [])
    if not isinstance(items, list):
        items = []

    item = {
        "file_id": metadata["file_id"],
        "file_name": metadata["file_name"],
        "metadata_path": f"{metadata['file_id']}.json",
    }

    items = [x for x in items if x.get("file_id") != metadata["file_id"]]
    items.append(item)
    items.sort(key=lambda x: (str(x.get("file_name", "")).lower(), x["file_id"]))
    safe_json_dump({"items": items}, index_path)


def process_one(
    source: Path,
    *,
    description: str,
    caption: str,
    tags: list[str],
    author: str,
    source_url: str,
    subject: str,
    data_dir: Path,
) -> dict[str, Any]:
    if not description.strip():
        raise ValueError("description must not be empty")
    if not caption.strip():
        raise ValueError("caption must not be empty")

    width, height = validate_image(source)
    file_id = str(uuid.uuid4())

    extension = source.suffix.lower()
    mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
    checksum = sha256_file(source)

    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / f"{file_id}{extension}"

    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    shutil_copy(source, destination)

    metadata = {
        "file_id": file_id,
        "file_name": source.name,
        "description": description,
        "caption": caption,
        "path": str(destination.resolve()),
        "data_url": file_uri(destination),
        "size": destination.stat().st_size,
        "extension": extension,
        "mime_type": mime_type,
        "width": width,
        "height": height,
        "created_at": now_iso(),
        "storage_type": "local",
        "checksum_algorithm": "sha256",
        "checksum": checksum,
        "tags": tags,
        "author": author,
        "source": source_url,
        "subject": subject,
    }

    json_path = Path.cwd() / f"{file_id}.json"
    try:
        safe_json_dump(metadata, json_path)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return metadata


def shutil_copy(source: Path, destination: Path) -> None:
    import shutil
    shutil.copy2(source, destination)


def verify_file(metadata_json: str | Path) -> tuple[str, str]:
    path = Path(metadata_json)
    if not path.exists():
        return "missing", f"Metadata not found: {path}"

    try:
        metadata = load_json(path)
    except Exception as exc:
        return "invalid", f"Cannot read metadata: {exc}"

    image_path = Path(str(metadata.get("path", "")))
    expected = str(metadata.get("checksum", ""))
    algorithm = str(metadata.get("checksum_algorithm", "")).lower()

    if not image_path.exists() or not image_path.is_file():
        return "missing", f"Image is missing or inaccessible: {image_path}"
    if algorithm != "sha256":
        return "invalid", f"Unsupported checksum algorithm: {algorithm}"

    try:
        actual = sha256_file(image_path)
    except OSError as exc:
        return "missing", f"Cannot read image: {exc}"

    if actual == expected:
        return "match", "Checksum matches; file integrity is OK."
    return "mismatch", f"Checksum mismatch: expected={expected}, actual={actual}"


def search_metadata(
    *,
    query: str = "",
    file_id: str = "",
    file_name: str = "",
    caption: str = "",
    tag: str = "",
    mime_type: str = "",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for json_path in sorted(Path.cwd().glob("*.json")):
        if json_path.name == INDEX_FILE:
            continue
        try:
            meta = load_json(json_path)
        except Exception:
            continue

        tags = [str(x).lower() for x in meta.get("tags", [])]
        blob = " ".join([
            str(meta.get("file_id", "")),
            str(meta.get("file_name", "")),
            str(meta.get("description", "")),
            str(meta.get("caption", "")),
            " ".join(tags),
            str(meta.get("mime_type", "")),
            str(meta.get("subject", "")),
        ]).lower()

        conditions = []
        if query:
            conditions.append(query.lower() in blob)
        if file_id:
            conditions.append(file_id.lower() in str(meta.get("file_id", "")).lower())
        if file_name:
            conditions.append(file_name.lower() in str(meta.get("file_name", "")).lower())
        if caption:
            conditions.append(caption.lower() in str(meta.get("caption", "")).lower())
        if tag:
            conditions.append(tag.lower() in tags)
        if mime_type:
            conditions.append(mime_type.lower() == str(meta.get("mime_type", "")).lower())

        if not conditions or all(conditions):
            results.append(meta)

    return results


def collect_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(p for p in input_path.iterdir() if is_image_file(p))
    raise FileNotFoundError(f"Input does not exist: {input_path}")



def print_header(title: str) -> None:
    print("\n" + "=" * 52)
    print(f"{title:^52}")
    print("=" * 52)


def prompt_nonempty(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Giá trị không được để trống.")


def prompt_metadata() -> dict[str, Any]:
    print("\nNhập metadata cho ảnh:")
    description = prompt_nonempty("Description: ")
    caption = prompt_nonempty("Caption: ")
    tags_text = input("Tags (phân cách bằng dấu phẩy, có thể bỏ trống): ").strip()
    author = input("Author (có thể bỏ trống): ").strip()
    source_url = input("Source (có thể bỏ trống): ").strip()
    subject = input("Subject (có thể bỏ trống): ").strip()
    return {
        "description": description,
        "caption": caption,
        "tags": [x.strip() for x in tags_text.split(",") if x.strip()],
        "author": author,
        "source_url": source_url,
        "subject": subject,
    }


def save_from_menu(batch: bool = False) -> None:
    print_header("EDUHUB - LƯU ẢNH" if not batch else "EDUHUB - LƯU NHIỀU ẢNH")
    raw = prompt_nonempty("Đường dẫn ảnh/thư mục: ")
    input_path = Path(raw.strip().strip('"'))
    try:
        sources = collect_inputs(input_path)
    except Exception as exc:
        print(f"[FAILED] {exc}")
        return

    if not sources:
        print("Không tìm thấy file ảnh hợp lệ trong đường dẫn đã chọn.")
        return

    if not batch and len(sources) > 1:
        sources = sources[:1]

    meta_input = prompt_metadata()
    success = 0
    failed = 0
    print(f"\nTìm thấy {len(sources)} ảnh. Đang xử lý...")
    for source in sources:
        try:
            meta = process_one(
                source,
                description=meta_input["description"],
                caption=meta_input["caption"],
                tags=meta_input["tags"],
                author=meta_input["author"],
                source_url=meta_input["source_url"],
                subject=meta_input["subject"],
                data_dir=Path("data"),
            )
            update_index(meta, Path.cwd() / INDEX_FILE)
            success += 1
            print(f"\n[SUCCESS] {source.name}")
            print(f"  File ID : {meta['file_id']}")
            print(f"  Storage : {meta['path']}")
            print(f"  JSON    : {meta['file_id']}.json")
            print(f"  Size    : {meta['size']} bytes")
            print(f"  Size px : {meta['width']}x{meta['height']}")
            print(f"  SHA-256 : {meta['checksum']}")
        except Exception as exc:
            failed += 1
            print(f"\n[SKIPPED] {source}: {exc}")
    print(f"\nKết quả: thành công={success}, lỗi={failed}, tổng={len(sources)}")


def search_from_menu() -> None:
    while True:
        print_header("EDUHUB - TÌM KIẾM METADATA")
        print("1. Từ khóa tổng hợp")
        print("2. File ID")
        print("3. Tên file")
        print("4. Caption")
        print("5. Tag")
        print("6. MIME type")
        print("0. Quay lại")
        choice = input("Chọn: ").strip()
        if choice == "0":
            return
        kwargs: dict[str, str] = {}
        labels = {
            "1": ("query", "Từ khóa"),
            "2": ("file_id", "File ID"),
            "3": ("file_name", "Tên file"),
            "4": ("caption", "Caption"),
            "5": ("tag", "Tag"),
            "6": ("mime_type", "MIME type"),
        }
        if choice not in labels:
            print("Lựa chọn không hợp lệ.")
            continue
        key, label = labels[choice]
        kwargs[key] = prompt_nonempty(f"{label}: ")
        results = search_metadata(**kwargs)
        print(f"\nTìm thấy {len(results)} kết quả:")
        if not results:
            print("Không có kết quả phù hợp.")
        for i, m in enumerate(results, 1):
            print(f"\n{i}. {m.get('file_name', '')}")
            print(f"   File ID : {m.get('file_id', '')}")
            print(f"   MIME    : {m.get('mime_type', '')}")
            print(f"   Caption : {m.get('caption', '')}")
            print(f"   Tags    : {', '.join(map(str, m.get('tags', [])))}")
            print(f"   Path    : {m.get('path', '')}")
        input("\nNhấn Enter để tiếp tục...")
        return


def verify_from_menu() -> None:
    print_header("EDUHUB - KIỂM TRA CHECKSUM")
    raw = prompt_nonempty("Metadata JSON (ví dụ abc.json): ")
    status, message = verify_file(raw.strip().strip('"'))
    print(f"\n[{status.upper()}] {message}")
    input("Nhấn Enter để quay lại menu...")


def view_metadata_from_menu() -> None:
    print_header("EDUHUB - XEM METADATA")
    raw = prompt_nonempty("File ID hoặc tên JSON: ")
    raw = raw.strip().strip('"')
    path = Path(raw)
    if path.suffix.lower() != ".json":
        path = Path(f"{raw}.json")
    if not path.exists():
        print(f"Không tìm thấy metadata: {path}")
    else:
        try:
            meta = load_json(path)
            print(json.dumps(meta, ensure_ascii=False, indent=2))
        except Exception as exc:
            print(f"Không đọc được metadata: {exc}")
    input("\nNhấn Enter để quay lại menu...")


def view_index_from_menu() -> None:
    print_header("EDUHUB - METADATA INDEX")
    path = Path(INDEX_FILE)
    if not path.exists():
        print("Chưa có metadata_index.json.")
    else:
        try:
            index = load_json(path)
            items = index.get("items", [])
            print(f"Tổng số item: {len(items)}\n")
            for i, item in enumerate(items, 1):
                print(f"{i}. {item.get('file_name', '')} | {item.get('file_id', '')} | {item.get('metadata_path', '')}")
        except Exception as exc:
            print(f"Không đọc được index: {exc}")
    input("\nNhấn Enter để quay lại menu...")


def menu_console() -> int:
    while True:
        print_header("EDUHUB IMAGE STORAGE SYSTEM")
        print("Storage: Local Folder")
        print("\n1. Lưu một ảnh")
        print("2. Lưu nhiều ảnh (batch)")
        print("3. Tìm kiếm metadata")
        print("4. Kiểm tra checksum")
        print("5. Xem metadata JSON")
        print("6. Xem metadata index")
        print("0. Thoát")
        choice = input("\nChọn chức năng: ").strip()

        if choice == "1":
            save_from_menu(batch=False)
        elif choice == "2":
            save_from_menu(batch=True)
        elif choice == "3":
            search_from_menu()
        elif choice == "4":
            verify_from_menu()
        elif choice == "5":
            view_metadata_from_menu()
        elif choice == "6":
            view_index_from_menu()
        elif choice == "0":
            print("\nĐã thoát EduHub. Hẹn gặp lại!")
            return 0
        else:
            print("Lựa chọn không hợp lệ. Vui lòng chọn lại.")


def main() -> int:
    if len(sys.argv) == 1:
        return menu_console()

    parser = argparse.ArgumentParser(description="EduHub Lab01 image metadata manager")
    parser.add_argument("input", nargs="?", help="One image or a directory")
    parser.add_argument("--description", default="")
    parser.add_argument("--caption", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--subject", default="")
    parser.add_argument("--data-dir", default="data")

    parser.add_argument("--verify", metavar="JSON")
    parser.add_argument("--search", action="store_true")
    parser.add_argument("--query", default="")
    parser.add_argument("--file-id", default="")
    parser.add_argument("--file-name", default="")
    parser.add_argument("--caption-search", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--mime-type", default="")
    args = parser.parse_args()

    if args.verify:
        status, message = verify_file(args.verify)
        print(f"[{status.upper()}] {message}")
        return 0 if status == "match" else 1

    if args.search:
        results = search_metadata(
            query=args.query,
            file_id=args.file_id,
            file_name=args.file_name,
            caption=args.caption_search,
            tag=args.tag,
            mime_type=args.mime_type,
        )
        print(f"Found {len(results)} result(s).")
        for m in results:
            print(f"- {m['file_id']} | {m['file_name']} | {m['mime_type']} | {m['data_url']}")
        return 0

    if not args.input:
        print("ERROR: input is required.")
        return 2
    if not args.description.strip() or not args.caption.strip():
        print("ERROR: --description and --caption are required and cannot be empty.")
        return 2

    try:
        sources = collect_inputs(Path(args.input))
    except Exception as exc:
        print(f"[FAILED] {exc}")
        return 1

    tags = [x.strip() for x in args.tags.split(",") if x.strip()]
    success = 0
    failed = 0

    print(f"Discovered {len(sources)} image file(s).")
    for source in sources:
        try:
            meta = process_one(
                source,
                description=args.description,
                caption=args.caption,
                tags=tags,
                author=args.author,
                source_url=args.source,
                subject=args.subject,
                data_dir=Path(args.data_dir),
            )
            update_index(meta, Path.cwd() / INDEX_FILE)
            success += 1
            print(f"[SUCCESS] {source.name}")
            print(f"  file_id={meta['file_id']}")
            print(f"  path={meta['path']}")
            print(f"  data_url={meta['data_url']}")
            print(f"  size={meta['size']} bytes")
            print(f"  dimensions={meta['width']}x{meta['height']}")
            print(f"  checksum={meta['checksum']}")
            print(f"  json={meta['file_id']}.json")
        except Exception as exc:
            failed += 1
            print(f"[SKIPPED] {source}: {exc}")

    print(f"Summary: success={success}, failed={failed}, total={len(sources)}")
    return 0 if failed == 0 else (0 if success > 0 else 1)


if __name__ == "__main__":
    raise SystemExit(main())
