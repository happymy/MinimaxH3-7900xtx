"""Adapt the verified RAW ComfyUI API workflows for Calliope.

The RAW files are known-good exports: they run, and their samplers, schedulers,
frame-count maths, VRAM guards and inlined official rewriter system prompts are
left exactly as authored. Only the two things Calliope needs are added.

1. Role tags in node titles - `(Input:prompt)`, `(Input:image)`, `(Output:video)`
   ... which `comfyui/parser.py` reads to build the dynamic form.
2. A patch target for the prompt. `comfyui/registry.py` decides which
   `inputs[...]` key a tagged node receives its value in, and for every
   generator node used here (`MiniMaxH3*`, `TextEncodeQwenImage21`,
   `ComfySwitchNode`) that mapping is not something Calliope can rely on. The
   established pattern - used by every shipped example workflow and by the
   hand-adapted library workflow - is to carry the prompt in a
   `PrimitiveStringMultiline`, which the registry maps correctly to `value`,
   and rewire the generator's real prompt input to it.

Two mechanical consequences of the RAW exports:

  * ComfyUI flattens subgraph nodes into composite ids like "459:451".
    `smart_fill._find_all_by_role` orders ref slots by node id, so those are
    renumbered to integers here (links rewritten to match).
  * i2v routes its frames through `ResizeImageMaskNode` before the generator, so
    tagging `LoadImage` directly is correct - the resize is untouched and keeps
    doing its job.

Everything else is deliberately left alone. Notably `ComfySwitchNode.switch`
keeps its authored value of `false`, which selects the literal `on_false`
branch and bypasses the inlined LLM rewriter: enabling it would load the 9B
prompt-encoder and change the VRAM profile these exports were verified at.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RAW = Path(r"D:\localAI\ComfyUI-last\plan\API_workflows\RAW")
TEST = RAW / "test"

# "459:451" -> 9451, keeping the tail visible and clear of the original ints.
ID_BASE = 9000
# Fresh ids for the inserted prompt carriers, clear of both.
NEW_ID_BASE = 9900


# --------------------------------------------------------------------------- #
# graph helpers
# --------------------------------------------------------------------------- #
def _rewrite_links(node: dict[str, Any], fn) -> None:
    """Apply ``fn`` to the source of every link in a node's inputs, in place.

    Compound keys (`ref_images.ref_image_0`, `resize_type.width`) hold links
    too - the value shape, not the key name, identifies a link.
    """
    for key, value in list(node.get("inputs", {}).items()):
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
            node["inputs"][key] = [fn(value[0]), value[1]]


def renumber_ids(wf: dict[str, Any]) -> dict[str, str]:
    """Map non-integer node ids to unique integers, rewriting all link targets."""
    reserved = {str(k) for k in wf if str(k).isdigit()}

    mapping: dict[str, str] = {}
    for key in wf:
        key = str(key)
        if key.isdigit():
            continue
        head, _, tail = key.rpartition(":")
        mapping[key] = str(ID_BASE + int(tail)) if tail.isdigit() else None
    if None in mapping.values():
        # Unexpected id shape: dense sequential remap instead.
        mapping = {}
        nxt = ID_BASE
        for key in wf:
            key = str(key)
            if key.isdigit():
                continue
            while str(nxt) in reserved:
                nxt += 1
            mapping[key] = str(nxt)
            nxt += 1

    for old, new in mapping.items():
        if new in reserved:
            raise SystemExit(f"id collision: {old} would become {new}, already in use")

    out: dict[str, Any] = {}
    for key, node in wf.items():
        key = str(key)
        if isinstance(node, dict):
            node = json.loads(json.dumps(node))  # deep copy; we rewrite in place
            _rewrite_links(node, lambda src: mapping.get(src, src))
        out[mapping.get(key, key)] = node
    return out, mapping


def _remap(mapping: dict[str, str]):
    """Translate a plan's pre-renumber node id to its post-renumber id."""

    def resolve(node_id: str) -> str:
        return mapping.get(str(node_id), str(node_id))

    return resolve


def require(wf: dict[str, Any], node_id: str, class_type: str | None = None) -> str:
    node = wf.get(str(node_id))
    if node is None:
        raise SystemExit(f"expected node {node_id} missing")
    if class_type and node.get("class_type") != class_type:
        raise SystemExit(
            f"node {node_id}: expected {class_type}, found {node.get('class_type')}"
        )
    return str(node_id)


def set_title(wf: dict[str, Any], node_id: str, title: str) -> None:
    wf[require(wf, node_id)].setdefault("_meta", {})["title"] = title


def add_prompt_input(
    wf: dict[str, Any],
    *,
    default: str,
    wire_to: str,
    wire_field: str,
    title: str = "(Input:prompt) Prompt",
) -> str:
    """Insert a tagged PrimitiveStringMultiline and point `wire_to.wire_field` at it."""
    target = wf[require(wf, wire_to)]
    previous = target["inputs"].get(wire_field)

    new_id = str(NEW_ID_BASE)
    n = 1
    while new_id in wf:
        n += 1
        new_id = str(NEW_ID_BASE + n)

    wf[new_id] = {
        "inputs": {"value": default},
        "class_type": "PrimitiveStringMultiline",
        "_meta": {"title": title},
    }
    target["inputs"][wire_field] = [new_id, 0]

    detail = ""
    if isinstance(previous, str):
        detail = f"  (replaced inline text, {len(previous)} chars)"
    elif previous is not None:
        detail = f"  (replaced link {previous[0]}[{previous[1]}])"
    print(f"      + {new_id} PrimitiveStringMultiline -> {wire_to}.{wire_field}{detail}")
    return new_id


def _load(name: str) -> tuple[dict[str, Any], Any]:
    wf = json.loads((RAW / name).read_text(encoding="utf-8"))
    wf, mapping = renumber_ids(wf)
    if mapping:
        print(f"      renumbered {len(mapping)} ids -> "
              f"{min(mapping.values())}..{max(mapping.values())}")
    return wf, _remap(mapping)


# --------------------------------------------------------------------------- #
# MiniMax H3
# --------------------------------------------------------------------------- #
def adapt_h3(name: str, plan: dict[str, Any]) -> dict[str, Any]:
    """H3 t2v / i2v / ref2v.

    `prompt` is a tagged literal on the generator; duration is tagged on the
    PrimitiveFloat, never on the generator's `length` - that input is wired to a
    ComfyMathExpression that quantises frames to the audio-aligned length, and
    writing it directly would desync sound from picture.
    """
    wf, rid = _load(name)

    model = require(wf, rid(plan["model"]), plan["model_class"])
    add_prompt_input(
        wf,
        default=plan["prompt_default"],
        wire_to=model,
        wire_field="prompt",
    )
    set_title(wf, rid(plan["duration"]), "(Input:duration) Duration")

    # Ref slots fill in node-id order; that order defines <Subject N> numbering.
    for nid, label in plan.get("images", []):
        set_title(wf, rid(nid), f"(Input:image) {label}")
    for nid, label in plan.get("videos", []):
        set_title(wf, rid(nid), f"(Input:video) {label}")
    for nid, label in plan.get("audios", []):
        set_title(wf, rid(nid), f"(Input:audio) {label}")

    set_title(wf, rid(plan["output"]), "(Output:video) Result")
    return wf


# --------------------------------------------------------------------------- #
# Qwen Image 2.1
# --------------------------------------------------------------------------- #
def adapt_qwen(name: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Qwen Image 2.1 t2i / edit / background-removal.

    `wire` names the node that actually holds the user-facing text, which
    differs per workflow:
      * t2i / edit route through PreviewAny <- ComfySwitchNode.on_false, the
        literal branch selected by the authored `switch = false`;
      * background-removal has no rewriter chain, the encoder prompt is a
        plain literal.
    Wiring the carrier at that same point keeps the switch, the previews and the
    (switch-disabled) rewriter exactly as the verified export had them.
    """
    wf, rid = _load(name)

    model = require(wf, rid(plan["model"]), "TextEncodeQwenImage21")
    wire_to, wire_field = plan["wire"]
    add_prompt_input(
        wf,
        default=plan["prompt_default"],
        wire_to=require(wf, rid(wire_to)),
        wire_field=wire_field,
    )

    for nid, label in plan.get("images", []):
        set_title(wf, rid(nid), f"(Input:image) {label}")

    set_title(wf, rid(plan["output"]), "(Output:image) Result")
    return wf


# --------------------------------------------------------------------------- #
# defaults
#
# Kept short and plain. Calliope rewrites a short brief into whichever section
# format the generator expects, so a long pre-baked prompt in the carrier would
# only be thrown away - and it would show up as a confusing prefilled default in
# the form.
# --------------------------------------------------------------------------- #
DEFAULT_PROMPTS = {
    "vaporwave": (
        "A vaporwave title sequence: chrome palm trees and a Greek statue "
        "against a pink and blue gradient sky, VHS tracking artifacts, retro "
        "electronic score."
    ),
    "cart": (
        "A baby sits in a shopping cart in a supermarket aisle, lifts a red "
        "apple and takes a big bite with exaggerated chewing sounds."
    ),
    "editorial": (
        "Greyscale fashion editorial portrait of a woman in black sunglasses "
        "and a high-neck dress with an optical camouflage pattern, against a "
        "lime-green and black-and-white collage background."
    ),
    "edit": "Replace the character's outfit with a light blue denim shirt.",
    "bgremove": "Remove the background and output the subject on a clean white background.",
}

ADAPT: dict[str, Any] = {
    # ---- MiniMax H3 -------------------------------------------------------- #
    "minimax_h3_t2v-gguf-8b-heretic-op.json": lambda: adapt_h3(
        "minimax_h3_t2v-gguf-8b-heretic-op.json",
        {
            "model": "129", "model_class": "MiniMaxH3ImageToVideo",
            "duration": "134", "output": "92",
            "prompt_default": DEFAULT_PROMPTS["vaporwave"],
        },
    ),
    "minimax_h3_i2v-gguf-8b-heretic-op.json": lambda: adapt_h3(
        "minimax_h3_i2v-gguf-8b-heretic-op.json",
        {
            "model": "133", "model_class": "MiniMaxH3ImageToVideo",
            "duration": "135", "output": "92",
            "prompt_default": DEFAULT_PROMPTS["vaporwave"],
            # Node-id order 114 < 141 is the documented ref-slot order. The
            # ResizeImageMaskNode between these and the generator is untouched.
            "images": [("114", "First Frame"), ("141", "Last Frame")],
        },
    ),
    "minimax_h3_ref2v-gguf-8b-heretic-op.json": lambda: adapt_h3(
        "minimax_h3_ref2v-gguf-8b-heretic-op.json",
        {
            "model": "145", "model_class": "MiniMaxH3ReferenceToVideo",
            "duration": "135", "output": "92",
            "prompt_default": DEFAULT_PROMPTS["cart"],
            "images": [("149", "Ref Image 1")],
            "videos": [("156", "Ref Video 1")],
            "audios": [("153", "Ref Audio 1")],
        },
    ),
    # ---- Qwen Image 2.1 --------------------------------------------------- #
    "qwen_image_2_1_t2i-Q8_0_gguf.json": lambda: adapt_qwen(
        "qwen_image_2_1_t2i-Q8_0_gguf.json",
        {
            "model": "459:452", "wire": ("459:474", "on_false"), "output": "461",
            "prompt_default": DEFAULT_PROMPTS["editorial"],
        },
    ),
    "qwen_image_2_1_image_edit-Q8_0_gguf.json": lambda: adapt_qwen(
        "qwen_image_2_1_image_edit-Q8_0_gguf.json",
        {
            "model": "459:474", "wire": ("459:484", "on_false"), "output": "461",
            "prompt_default": DEFAULT_PROMPTS["edit"],
            "images": [("470", "Source"), ("475", "Reference 2")],
        },
    ),
    "qwen_image_2_1_background_removal-Q8_0_gguf.json": lambda: adapt_qwen(
        "qwen_image_2_1_background_removal-Q8_0_gguf.json",
        {
            "model": "459:474", "wire": ("459:474", "prompt"), "output": "461",
            "prompt_default": DEFAULT_PROMPTS["bgremove"],
            "images": [("470", "Source")],
        },
    ),
}


def main() -> None:
    TEST.mkdir(parents=True, exist_ok=True)
    for name, build in ADAPT.items():
        print(f"\n=== {name}")
        wf = build()
        dst = TEST / name
        dst.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"      -> {dst.name}  ({len(wf)} nodes)")
    print(f"\ndone -> {TEST}")


if __name__ == "__main__":
    main()