"""PowerShell-friendly maintenance CLI for Sketch Search indexes and debug."""

import argparse
from pathlib import Path
import shutil

from scripts.paths import PROJECT_ROOT
from scripts.texture_signature.batch import (
    TextureBatchError,
    TextureSource,
    process_hog_textures,
    resolve_textures,
)
from scripts.texture_signature.config import EDGE_METHODS, HOG_BINS, HOG_CELL_SIZE
from scripts.texture_signature.eligibility import expected_texture_size
from scripts.texture_signature.hog_index import block_hog_index_path, build_block_hog_index


DEBUG_ROOT = PROJECT_ROOT / "debug"


def _positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain Sketch Search HOG features.")
    modes = parser.add_subparsers(dest="mode", required=True)

    hog = modes.add_parser("hog", help="build fixed HOG12 signatures")
    hog.add_argument("selection_mode", choices=("selected", "all"))
    hog.add_argument("object_type", choices=("block",))
    hog.add_argument("names", nargs="*", metavar="NAME")
    hog.add_argument("--edge-method", choices=EDGE_METHODS, default="sobel")
    hog.add_argument("--limit", type=_positive_integer)
    hog.add_argument("--debug", action="store_true")

    hog_index = modes.add_parser("hog-index", help="build one production block index")
    hog_index.add_argument("object_type", choices=("block",))
    hog_index.add_argument("--edge-method", choices=EDGE_METHODS, default="sobel")

    rebuild = modes.add_parser("rebuild-indexes", help="rebuild Sobel and Canny indexes")
    rebuild.add_argument("object_type", choices=("block",))
    modes.add_parser("clean-debug", help="remove generated files under debug only")
    return parser


def _progress(index: int, total: int, item: TextureSource) -> None:
    print(f"[{index}/{total}] {item.name:.<36} OK")


def _skipped(index: int, total: int, item: TextureSource, size: tuple[int, int]) -> None:
    expected = expected_texture_size(item.object_type)
    print(
        f"[{index}/{total}] {item.name:.<36} "
        f"SKIPPED ({size[0]}x{size[1]}, expected {expected[0]}x{expected[1]})"
    )


def _build_index(edge_method: str, *, show_progress: bool = True) -> None:
    print(f"Building {edge_method.upper()} HOG block index...")
    index, result = build_block_hog_index(
        edge_method=edge_method,
        on_complete=_progress if show_progress else None,
        on_skip=_skipped if show_progress else None,
    )
    path = block_hog_index_path(edge_method)
    print(f"Processed: {len(result.signatures)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Feature size: {index.features.shape[1]}")
    print(f"Saved: {path.relative_to(PROJECT_ROOT).as_posix()}\n")


def _clean_debug() -> None:
    expected = (PROJECT_ROOT / "debug").resolve()
    if DEBUG_ROOT.resolve() != expected or expected.parent != PROJECT_ROOT.resolve():
        raise TextureBatchError("Refusing to clean an unexpected debug path.")
    if DEBUG_ROOT.exists():
        for child in DEBUG_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    print("Cleaned: debug/")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "clean-debug":
            _clean_debug()
            return 0
        if args.mode == "rebuild-indexes":
            for method in EDGE_METHODS:
                _build_index(method, show_progress=False)
            return 0
        if args.mode == "hog-index":
            _build_index(args.edge_method)
            return 0

        hog_mode = args.mode == "hog"
        all_mode = hog_mode and args.selection_mode == "all"
        names = None if all_mode else args.names
        if hog_mode and not all_mode and not names:
            raise TextureBatchError("Select at least one material.")
        if hog_mode and all_mode and args.names:
            raise TextureBatchError("The 'all' HOG mode does not accept material names.")

        textures = resolve_textures(args.object_type, names)
        if all_mode and args.limit is not None:
            textures = textures[: args.limit]
        print("Texture Signature Pipeline\n")
        print(f"Type: {args.object_type}")
        print(f"Mode: {args.mode}")
        if hog_mode:
            print(f"Edge method: {args.edge_method}")
            print(f"HOG: cells {HOG_CELL_SIZE}x{HOG_CELL_SIZE}, {HOG_BINS} bins")
        print(f"Textures: {len(textures)}")
        print(f"Debug output: {'enabled' if args.debug else 'disabled'}\n")

        if hog_mode:
            result = process_hog_textures(
                textures,
                edge_method=args.edge_method,
                debug=args.debug,
                skip_ineligible=all_mode,
                on_complete=_progress,
                on_skip=_skipped,
            )
            print(f"\nProcessed: {len(result.signatures)}")
            print(f"Skipped: {len(result.skipped)}")
        print("\nDone.")
        if args.debug:
            suffix = f"/<material>/{args.edge_method}/" if hog_mode else "/"
            print(f"Debug: debug/texture_signature/{args.object_type}{suffix}")
        return 0
    except (TextureBatchError, ValueError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
