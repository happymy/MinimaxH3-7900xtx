"""Cache /object_info down to the bits the UI->API converter needs: per class, the
input names in declaration order, the widget-typed subset, and the set of
link-typed names. Autogrow sockets are stored by the frontend as `name.1`,
`name.2`, ... so the base name is what the API expects."""
import json, os, sys, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_schema.json")
LINKY = {"IMAGE", "LATENT", "MODEL", "CLIP", "VAE", "CONDITIONING", "MASK", "CONTROL_NET",
         "CLIP_VISION", "AUDIO", "GLIGEN", "GLIGEN_ACC", "SAMPLER", "GUIDER", "NOISE",
         "SIGMAS", "UPSCALE_MODEL", "PHOTOMAKER", "STYLE_MODEL", "BBOX_DETECTOR",
         "SEGM_DETECTOR", "VOICE_CLONE", "TTS_MODEL", "FACE_MODEL", "IMAGE_NOISE"}

raw = json.loads(urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=180).read())

schema = {}
for name, d in raw.items():
    order, widgets, names = [], [], set()
    wtypes, wopts, wdyn, agrow, wcombo = {}, {}, {}, [], []
    for sect in ("required", "optional"):
        for k, v in ((d.get("input") or {}).get(sect) or {}).items():
            t = v[0] if isinstance(v, (list, tuple)) and v else k
            opts = v[1] if isinstance(v, (list, tuple)) and len(v) > 1 else None
            t = t if isinstance(t, str) else "COMBO"
            # a combo's second element is either the option list or a config dict;
            # a dynamic combo carries its per-option sub-widgets under "options"
            if t == "COMFY_DYNAMICCOMBO_V3":
                o = opts.get("options") if isinstance(opts, dict) else None
                opts = [x["key"] for x in o] if isinstance(o, list) else None
                if isinstance(o, list):
                    wdyn[k.split(".")[0]] = {
                        x["key"]: list((x.get("inputs") or {}).get("required", {}))
                                + list((x.get("inputs") or {}).get("optional", {}))
                        for x in o if "key" in x}
            elif t == "COMBO" and not isinstance(opts, list):
                opts = None
            if t == "COMBO" and isinstance(opts, list):
                opts = [o.get("name") if isinstance(o, dict) else o for o in opts]
            base = k.split(".")[0]
            if base not in names:
                order.append(base)
                names.add(base)
            if t == "COMFY_AUTOGROW_V3":
                agrow.append(base)
            else:
                if t == "COMFY_DYNAMICCOMBO_V3":
                    wcombo.append(base)
                if t not in LINKY and not base.startswith("control_after_generate"):
                    widgets.append(base)
                    wtypes[base] = "COMBO" if t == "COMFY_DYNAMICCOMBO_V3" else t
                    wopts[base] = opts if wtypes[base] == "COMBO" else None
    schema[name] = {"order": order, "widgets": widgets, "inputs": sorted(names),
                    "wtypes": wtypes, "wopts": wopts, "wdyn": wdyn, "agrow": agrow,
                    "wcombo": wcombo,
                    "output_node": bool(d.get("output_node"))}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(schema, f, indent=1)
print("%d classes -> %s" % (len(schema), OUT))
for k in ("LoadImage", "SaveImageAdvanced", "TextEncodeQwenImage21", "UnetLoaderGGUF",
          "UNETLoader", "CLIPLoader", "QwenImage21Cache", "ComfySwitchNode", "KSampler",
          "ImageCompare", "EmptyLatentImage", "ResolutionSelector"):
    s = schema.get(k)
    print("  %-22s %s" % (k, json.dumps(s["widgets"]) if s else "MISSING"))
