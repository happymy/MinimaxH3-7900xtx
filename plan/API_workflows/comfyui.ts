const rules = [
  {
    type: "input",
    field: "baseUrl",
    title: "ComfyUI 地址",
    value: "http://127.0.0.1:8188",
    props: { placeholder: "http://127.0.0.1:8188" },
  },
] as const;

const version = "2.0.0";

const imageTimeout = 20 * 60 * 1000;
const videoTimeout = 60 * 60 * 1000;

const ratioLabels = {
  "1:1": "1:1 (Square)",
  "2:3": "2:3 (Portrait Photo)",
  "3:2": "3:2 (Photo)",
  "3:4": "3:4 (Portrait Standard)",
  "4:3": "4:3 (Standard)",
  "9:16": "9:16 (Portrait Widescreen)",
  "16:9": "16:9 (Widescreen)",
  "21:9": "21:9 (Ultrawide)",
};

const mimeExtensions = {
  "image/png": ".png",
  "image/jpeg": ".jpg",
  "image/webp": ".webp",
  "image/gif": ".gif",
  "image/bmp": ".bmp",
  "image/avif": ".avif",
  "video/mp4": ".mp4",
  "video/quicktime": ".mov",
  "video/webm": ".webm",
  "audio/mpeg": ".mp3",
  "audio/mp4": ".m4a",
  "audio/wav": ".wav",
  "audio/flac": ".flac",
  "audio/ogg": ".ogg",
  "audio/opus": ".opus",
};

const templates = {
  qwenT2i:   {
    "13": {
      "inputs": {
        "aspect_ratio": "1:1 (Square)",
        "megapixels": 1,
        "multiple": 8
      },
      "class_type": "ResolutionSelector",
      "_meta": {
        "title": "分辨率选择器"
      }
    },
    "461": {
      "inputs": {
        "filename_prefix": "Qwen_image_2.1",
        "format": "png",
        "format.bit_depth": "8-bit",
        "format.input_color_space": "sRGB",
        "images": [
          "459:457",
          0
        ]
      },
      "class_type": "SaveImageAdvanced",
      "_meta": {
        "title": "保存图像（高级）"
      }
    },
    "459:451": {
      "inputs": {
        "unet_name": "qwen-image-2.1-UC-Q8_0.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "459:452": {
      "inputs": {
        "prompt": [
          "459:472",
          0
        ],
        "negative_prompt": "",
        "resolution": 1024,
        "clip": [
          "459:453",
          0
        ]
      },
      "class_type": "TextEncodeQwenImage21",
      "_meta": {
        "title": "Text Encode Qwen Image 2.1"
      }
    },
    "459:453": {
      "inputs": {
        "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
        "type": "qwen_image",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {
        "title": "加载CLIP"
      }
    },
    "459:454": {
      "inputs": {
        "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "459:456": {
      "inputs": {
        "width": [
          "13",
          0
        ],
        "height": [
          "13",
          1
        ],
        "batch_size": 1
      },
      "class_type": "EmptyLatentImage",
      "_meta": {
        "title": "空Latent图像"
      }
    },
    "459:457": {
      "inputs": {
        "samples": [
          "459:458",
          0
        ],
        "vae": [
          "459:454",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "459:458": {
      "inputs": {
        "seed": 447606998181262,
        "steps": 25,
        "cfg": 2,
        "sampler_name": "euler",
        "scheduler": "simple",
        "denoise": 1,
        "model": [
          "459:483",
          0
        ],
        "positive": [
          "459:452",
          0
        ],
        "negative": [
          "459:452",
          1
        ],
        "latent_image": [
          "459:456",
          0
        ]
      },
      "class_type": "KSampler",
      "_meta": {
        "title": "K采样器"
      }
    },
    "459:471": {
      "inputs": {
        "prompt": "Greyscale fashion editorial portrait of an avant-garde woman tilted upwards in profile, captured with striking high-contrast chiaroscuro lighting. She wears oversized, thick-rimmed circular black sunglasses with matte dark lenses, concealing her upward gaze. Her attire merges high couture with tactical abstraction: a high-necked structural dress tailored from heavyweight fabric featuring a disrupted optical camouflage pattern—interlocking oversized polka dots, pixelated stippling, and organic contour blotches in stark monochrome that mimic military disruptive patterns in a refined runway style. Around her shoulders, asymmetric pleated webbing and tailored cargo straps are integrated seamlessly into the garment’s architecture. In her gloved hand, she clutches a structured matte-leather geometric handbag accented with subtle tactical buckles, utility stitching, and dark brushed-metal hardware. Her skin texture is rendered with hyper-detailed clarity, sculpted by intense, razor-sharp studio key light and deep graphite shadows. The striking background is a vivid mixed-media graphic collage, composed of flat vibrant lime green planes, stark black and white overlapping circles, segmented semi-circles with bold zebra striping, dense micro-halftone dot matrices, and vector topographic contour lines. The clash between monochromatic disruptive camo elements on her clothing and the saturated, retro-futuristic pop-art backdrop creates an intense visual dissonance, emphasizing sharp silhouettes, paper cut-out edges, dynamic compositional balance, and clean graphic novel textures. Absolutely no text, no typography, no letters, no words, no numbers, no logos, no watermark, no captions, pure imagery only.",
        "max_length": 16256,
        "sampling_mode": "on",
        "sampling_mode.temperature": 1,
        "sampling_mode.top_k": 20,
        "sampling_mode.top_p": 0.95,
        "sampling_mode.min_p": 0,
        "sampling_mode.repetition_penalty": 1.05,
        "sampling_mode.seed": 447606998181262,
        "sampling_mode.presence_penalty": 0,
        "thinking": false,
        "use_default_template": false,
        "mtp": "auto",
        "clip": [
          "459:473",
          0
        ],
        "system_prompt": [
          "459:475",
          0
        ]
      },
      "class_type": "TextGenerate",
      "_meta": {
        "title": "TextGenerate"
      }
    },
    "459:472": {
      "inputs": {
        "source": [
          "459:474",
          0
        ]
      },
      "class_type": "PreviewAny",
      "_meta": {
        "title": "预览任意"
      }
    },
    "459:473": {
      "inputs": {
        "clip_name": "qwen3.5_9b_qwen_image_2.1_pe_t2i.int8_convrot.safetensors",
        "type": "stable_diffusion",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {
        "title": "加载CLIP"
      }
    },
    "459:474": {
      "inputs": {
        "switch": false,
        "on_false": "Greyscale fashion editorial portrait of an avant-garde woman tilted upwards in profile, captured with striking high-contrast chiaroscuro lighting. She wears oversized, thick-rimmed circular black sunglasses with matte dark lenses, concealing her upward gaze. Her attire merges high couture with tactical abstraction: a high-necked structural dress tailored from heavyweight fabric featuring a disrupted optical camouflage pattern—interlocking oversized polka dots, pixelated stippling, and organic contour blotches in stark monochrome that mimic military disruptive patterns in a refined runway style. Around her shoulders, asymmetric pleated webbing and tailored cargo straps are integrated seamlessly into the garment’s architecture. In her gloved hand, she clutches a structured matte-leather geometric handbag accented with subtle tactical buckles, utility stitching, and dark brushed-metal hardware. Her skin texture is rendered with hyper-detailed clarity, sculpted by intense, razor-sharp studio key light and deep graphite shadows. The striking background is a vivid mixed-media graphic collage, composed of flat vibrant lime green planes, stark black and white overlapping circles, segmented semi-circles with bold zebra striping, dense micro-halftone dot matrices, and vector topographic contour lines. The clash between monochromatic disruptive camo elements on her clothing and the saturated, retro-futuristic pop-art backdrop creates an intense visual dissonance, emphasizing sharp silhouettes, paper cut-out edges, dynamic compositional balance, and clean graphic novel textures. Absolutely no text, no typography, no letters, no words, no numbers, no logos, no watermark, no captions, pure imagery only.",
        "on_true": [
          "459:471",
          0
        ]
      },
      "class_type": "ComfySwitchNode",
      "_meta": {
        "title": "切换"
      }
    },
    "459:475": {
      "inputs": {
        "value": "<|im_start|>system\n# Image Prompt Rewriting Expert\n\nYou turn a user's image request into one long English paragraph that describes the\nfinished image as if you were looking at it, plus the aspect ratio it should be\nrendered at. You are not talking to the user and not talking to a renderer: you are\nan observer reporting what is in the frame.\n\nWork through the eight steps below in order. Each step commits one decision; later\nsteps never revise an earlier one.\n\n## Step 1 — Read the brief and split it in two\n\nList what the user has fixed and what they have left open.\n\nFixed, and it must survive into your description unchanged: every string of text\nthey want shown, every named object, every count, every stated colour, every stated\nposition, and the aspect ratio if they gave one. Copy their text strings character\nfor character, in their own script, including punctuation and spacing.\n\nA third thing they may give you is an instruction about the job rather than about the\npicture — \"use double quotes\", \"no hard-edged blocks\", \"4K, no noise\", \"make sure the\ntext is sharp\". That is not content. Obey it silently where it applies and never echo\nit: the description states what is in the frame, never what must be done.\n\nOpen, and you must decide it: everything they did not mention. A three-word request\nand a three-hundred-word request both become a description of the same size, so a\nshort brief means you are inventing most of the frame, not writing less.\n\n## Step 2 — Fix the frame\n\nDecide the orientation from the subject, then pick the ratio.\n\nIf the user states a ratio, use it. Otherwise: `3:2` for anything horizontal and\n`2:3` for anything vertical — these are the two defaults and cover most images.\nUse `1:1` for a square badge, icon, album cover or single centred emblem, `16:9`\nfor a wide cinematic or presentation frame, `1:2` or `9:16` for a phone screen or a\ntall standing banner. `3:4`, `2:1`, `21:9`, `4:3`, `9:21`, `4:5`, `3:1`, `5:4`,\n`1:3` exist but only when the subject or the user really calls for them.\n\nThe ratio lives only in the `wh_ratio` field. Never write a ratio, a resolution, or\na pixel count into the description itself.\n\n## Step 3 — Write the opening sentence\n\nOne sentence, around twenty words. Name the medium, the style, the subject, and the\nbackground or palette; usually name the orientation too:\n\n`The image is a ⟨vertical / wide / square / tall⟩ ⟨style⟩ ⟨photograph · poster · illustration · scene · portrait · infographic · close-up · graphic · page · card · sheet · logo⟩ of ⟨subject⟩, ⟨the background and its palette⟩.`\n\n`This is a …` or a bare `A vertical realistic photograph of …` work equally well. The\nmedium noun is the one part that is never omitted.\n\nThe style word goes here — realistic, photorealistic, minimalist, flat-vector,\ncinematic, watercolour, isometric, editorial, hand-drawn, 3D-rendered, retro. Name\nit once here; you may echo it in the closing sentence.\n\n## Step 4 — Inventory before you write\n\nBefore any more prose, settle two lists.\n\nEvery element that will appear, each with a place in the frame: upper-left,\nacross the top, on the far right, in the lower-third, in the centre, in front of,\nbehind, tucked into the corner. You will need eight to fourteen such positional\nphrases, about ten typically, and they must reach the corners, the edges and the\ncentre — not cluster in the middle.\n\nEvery piece of text that will be legible in the image, in reading order.\n\n## Step 5 — Walk the frame\n\nNow describe it in order. Which order depends on how the frame is filled.\n\n**If the frame is divided into regions** — a poster, a page, an interface, a layout, a\nwide scene with several things in it — walk the regions:\n\n1. The background and the surface it sits on — this comes immediately after the\n   opening sentence, not at the end.\n2. The top band: headline, header bar, sky, ceiling, whatever occupies the top edge.\n3. Down and across the body of the frame: left side, then centre, then right side.\n   Give each region one or two sentences.\n4. The bottom band: footer, foreground, ground plane, base row.\n\n**If one subject fills the frame** — a portrait, a close-up, a single object — walk\nthe subject instead: the background and how far it falls off, then the subject's pose\nand where it is placed in the frame, then head and face, then body and each garment or\nsurface, then what is held or touching it, then whatever little is left at the edges.\nKeep using positional phrases inside the subject — in the upper-left of the frame,\nbehind the left shoulder, along the lower edge — so the frame stays locatable.\n\nRoughly a third of your sentences should open on the positional phrase itself —\n\"On the right side of the frame, …\", \"In the upper-left corner, …\", \"Across the\nlower third, …\" — so the reader always knows where they are looking.\n\nKeep it to one paragraph. Break to a new paragraph only when the image is genuinely\nbuilt from stacked regions — panels, cards, sections, slides — and then one\nparagraph per region, each opening on where that region sits.\n\n## Step 6 — Set every piece of text\n\nSkip this step if nothing in the image is meant to be read — a third of images have\nno legible text at all, and inventing signage for them is a mistake.\n\nOtherwise, for each string from your Step 4 list, in reading order, name where it sits,\nwhat it looks like, and what it says: `a bold black headline across the top reads \"…\"`.\n\nPut the string in straight double quotes, in its own script — Chinese, Russian,\nKorean, Japanese and Arabic text stays in Chinese, Russian, Korean, Japanese and\nArabic. Give its weight, colour, case and relative size. Describe a line break as a\nsecond line rather than putting a real newline inside the string. If a mark is not meant\nto be read — distant signage, a label behind glass, dense body copy — call it\nblurred, indistinct, or too small to read rather than inventing letters. If the image contains a chart\nor a table, its axes, tick labels, legend entries, series and cell values are text\ntoo: write them out.\n\n## Step 7 — Give the lighting its own sentence\n\nEvery image has light in it, and the description always accounts for it: the source,\nits direction, its quality, and the shadows and highlights it leaves. Soft diffused\ndaylight from a window on the left, hard overhead studio light, warm low sun, flat\neven ambient light for a diagram.\n\nOnce the contents are placed, give it a sentence of its own — `The lighting is …` —\nor, if the light is what makes a particular surface look the way it does, fold it into\nthat surface's sentence. Either way it is stated explicitly, not left implied.\n\n## Step 8 — Close with the whole frame\n\nEnd on a single sentence that steps back:\n\n`The overall composition ⟨is / uses / feels⟩ …`\n\n`The composition is …`, `The overall design …`, `The overall mood …`, `The overall\npalette …` and `The image has …` are the same move. Cover balance and symmetry, the\npalette, the style, and the mood in that one sentence. Write exactly one such\nsentence — do not follow it with a second summary.\n\n## Throughout\n\n**Size.** The description runs about twenty sentences and four to five hundred words,\nroughly twenty-five words a sentence. That is the same size whether the brief was three\nwords or three hundred: a dense frame with many regions and a lot of text runs longer, a\nsingle quiet subject runs shorter, but a thin brief never buys a thin description.\n\n**Observe, don't instruct.** Present tense, third person, declarative. No \"you\", no\n\"create\", no \"make sure\", no \"the AI should\". No quality boosters — no \"masterpiece\",\n\"8K\", \"highly detailed\", \"award-winning\".\n\n**Hedge what you cannot be certain of.** An observer describing a picture says\n\"appears to be\", \"likely\", \"suggesting\", and offers a pair — \"a notebook\nor a tablet\", \"wood or dark laminate\" — when the thing is genuinely ambiguous. Do\nthis often; it is the natural register here. Be flatly definite only about what the\nuser fixed.\n\n**Name colours with a modifier, almost never bare.** Deep navy, muted olive, pale\ncream, warm terracotta, soft dusty rose, blue-grey, off-white, charcoal, brownish-\ngreen. Hex codes only if the user gave them.\n\n**Give the material, not just the noun.** Brushed metal, matte plastic, glossy\nceramic, coarse linen, weathered wood, frosted glass, grain, scuffs, condensation,\nvisible brush strokes, paper fibre.\n\n**Enumerate; never summarise.** \"Several items\" and \"various decorations\" are not\ndescriptions. Say what each thing is. Write small counts as words — three, five,\ntwelve — and if something is partly hidden, say so and describe the visible part.\n\n**People get their observable surface.** Build, posture, where they are looking,\nexpression, hair, skin tone, and each garment with its colour and material. Age is a\nlife stage or a decade — a child, a teenager, a young adult, middle-aged, elderly,\nin her thirties — never a number of years. If a face is turned away or cropped, say\nthat instead of describing it.\n\n**Objects by class, not by brand.** A silver laptop, a mirrorless camera, a compact\nhatchback — unless the user named the brand. Photographic and design vocabulary is\nwelcome: shallow depth of field, bokeh, backlit, close-up, negative space,\ngrid, drop shadow.\n\n**Everything holds together physically.** Shadows fall away from the light, reflections\nmatch what is in front of the surface, scale is consistent between neighbouring\nobjects, and a surface reacts to what sits on it. If the user asked for something\nimpossible, describe it as the image shows it and let the rest of the scene stay\ncoherent around it.\n\n## Language\n\nThe description is always in English, whatever language the request arrives in. The\nonly exception is text shown inside the image, which stays in its own script.\n\n## Output format\n\n- Return the description and nothing else: one continuous paragraph of English, in a single line\nstarting on the very first character of your reply.\n- No JSON, no braces, no key names, no labels, no headings, no markdown, no code fences, and no quotation marks around the paragraph.\n- No preamble, no acknowledgement, no explanation, no summary, no notes, no closing remarks, no questions.\n- No ratio, no resolution, no pixel count, no timestamps.\n\nYour whole reply is used as the image prompt, so every extra word you add becomes part of the image.\n<|im_end|>"
      },
      "class_type": "PrimitiveStringMultiline",
      "_meta": {
        "title": "Text (System Prompt)"
      }
    },
    "459:480": {
      "inputs": {
        "device": "auto",
        "dtype": "default",
        "model": [
          "459:451",
          0
        ]
      },
      "class_type": "QwenImage21Cache",
      "_meta": {
        "title": "Qwen Image 2.1 Cache"
      }
    },
    "459:483": {
      "inputs": {
        "shift": 3.1000000000000005,
        "sampling": "flow",
        "model": [
          "459:480",
          0
        ]
      },
      "class_type": "ModelSamplingAuraFlow",
      "_meta": {
        "title": "采样算法（AuraFlow）"
      }
    }
  },
  qwenImageEdit:   {
    "461": {
      "inputs": {
        "filename_prefix": "Qwen_image_2.1",
        "format": "png",
        "format.bit_depth": "8-bit",
        "format.input_color_space": "sRGB",
        "images": [
          "459:457",
          0
        ]
      },
      "class_type": "SaveImageAdvanced",
      "_meta": {
        "title": "保存图像（高级）"
      }
    },
    "470": {
      "inputs": {
        "image": "portrait_model_denim.png"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "加载图像"
      }
    },
    "472": {
      "inputs": {
        "compare_view": {
          "__value__": [
            "",
            ""
          ]
        },
        "image_a": [
          "470",
          0
        ],
        "image_b": [
          "461",
          0
        ]
      },
      "class_type": "ImageCompare",
      "_meta": {
        "title": "图像对比"
      }
    },
    "475": {
      "inputs": {
        "image": "clothing_light_blue_denim_shirt.png"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "加载图像"
      }
    },
    "459:451": {
      "inputs": {
        "unet_name": "qwen-image-2.1-UC-Q8_0.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "459:453": {
      "inputs": {
        "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
        "type": "qwen_image",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {
        "title": "加载CLIP"
      }
    },
    "459:454": {
      "inputs": {
        "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "459:456": {
      "inputs": {
        "width": 1024,
        "height": 1024,
        "batch_size": 1
      },
      "class_type": "EmptyLatentImage",
      "_meta": {
        "title": "空Latent图像"
      }
    },
    "459:457": {
      "inputs": {
        "samples": [
          "459:458",
          0
        ],
        "vae": [
          "459:454",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "459:458": {
      "inputs": {
        "seed": 1095460012924539,
        "steps": 25,
        "cfg": 2,
        "sampler_name": "euler",
        "scheduler": "simple",
        "denoise": 1,
        "model": [
          "459:501",
          0
        ],
        "positive": [
          "459:474",
          0
        ],
        "negative": [
          "459:474",
          1
        ],
        "latent_image": [
          "459:468",
          0
        ]
      },
      "class_type": "KSampler",
      "_meta": {
        "title": "K采样器"
      }
    },
    "459:468": {
      "inputs": {
        "switch": false,
        "on_false": [
          "459:474",
          2
        ],
        "on_true": [
          "459:456",
          0
        ]
      },
      "class_type": "ComfySwitchNode",
      "_meta": {
        "title": "切换"
      }
    },
    "459:469": {
      "inputs": {
        "device": "auto",
        "dtype": "default",
        "model": [
          "459:451",
          0
        ]
      },
      "class_type": "QwenImage21Cache",
      "_meta": {
        "title": "Qwen Image 2.1 Cache"
      }
    },
    "459:474": {
      "inputs": {
        "prompt": [
          "459:480",
          0
        ],
        "negative_prompt": "",
        "resolution": 0,
        "clip": [
          "459:453",
          0
        ],
        "images.image_1": [
          "470",
          0
        ],
        "vae": [
          "459:454",
          0
        ],
        "images.image_2": [
          "475",
          0
        ]
      },
      "class_type": "TextEncodeQwenImage21",
      "_meta": {
        "title": "Text Encode Qwen Image 2.1"
      }
    },
    "459:477": {
      "inputs": {
        "clip_name": "qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors",
        "type": "qwen_image",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {
        "title": "加载CLIP"
      }
    },
    "459:479": {
      "inputs": {
        "value": "# Edit Prompt Enhancer — General (v2, 精简版)\n\n**FIRST — there are TWO separate language decisions. Do NOT conflate them.**\n\n**(A) Language of the rewritten prompt's DESCRIPTIVE prose — every word OUTSIDE double quotes (the description you write for the diffusion model, NOT the text painted into the image). This decision is final and non-negotiable:**\n- User instruction is in Chinese → write the description in Chinese.\n- User instruction is in English → write the description in English.\n- User instruction is in ANY other language (Japanese, Korean, French, Spanish, Thai, etc.) → write the description in English.\n\n**(B) Language of the TEXT THAT WILL BE RENDERED INTO THE OUTPUT IMAGE — the content INSIDE double quotes. Decide it in this strict priority order:**\n1. If the user's instruction gives the exact text to write, OR names a target language for the text (e.g. \"改成'夏日特惠'\", \"把标题写成英文\", \"add a Japanese title\", \"write the caption in Thai\") → render exactly that text / in exactly that specified language.\n2. Otherwise, if the input image already contains text → render in the DOMINANT language of the image's existing text — even when the instruction is written in a different language.\n3. Otherwise (the image contains no text AND the instruction names no target language) → render in the language of the user's instruction itself — including Japanese, Korean, Thai, Arabic, French, etc. Do NOT force it to English.\nWorked example: image is mostly Thai, instruction is in English asking to add/redesign a title without giving the exact words or a language → the rendered (quoted) text must be **Thai** (the image's dominant language), while the surrounding description (A) is still written in English.\n\nTwo reinforcements on decision (B): all rendered (quoted) text must be **monolingual** — do not mix Chinese and English inside the quotes and do not emit a bilingual pair unless the user explicitly asks for one. And **genre never overrides input language**: a \"spec sheet / cinematic data-document / storyboard / technical parameter\" look is achieved through layout and typography, NOT by switching rendered labels to English — every header, label, and caption stays in the decided language (standardized units and user-given proper nouns may remain Latin).\n\nYou are an expert at clarifying image editing instructions. Given a user's vague or ambiguous edit instruction and the input image(s), rewrite it into a precise, unambiguous, actionable editing directive. An input image is ALWAYS present — this is always an image-editing task, never text-to-image from nothing.\n\n## Core Objective\n\nRewrite the instruction so a downstream image-editing model can execute it without guessing — anchored on what the input image(s) actually show, faithful to the user's intent, inventing nothing.\n\n**How much you build is intent-branched.** When the user wants *this picture changed* (a local object/attribute/background edit, a text or UI edit, a quality or style change, a viewpoint/canvas transform), clarify and constrain: say exactly what changes, and let everything else stand. When the user wants *a new picture of this subject* (placing a subject in a new scene, compositing across images, a photo-shoot or poster or infographic built from a reference), construct actively: design the scene, lighting, composition and layout to a professional standard. Scale the elaboration to what was asked — a plain placement stays restrained, a styled shoot or a publication-grade poster is built out fully.\n\n## The Governing Principle — Attribute Disentanglement at Full Strength\n\n**Edit exactly the attribute(s) the user named, push each to a strong and unmistakable degree, and hold everything else at input fidelity.**\n\nBoth halves matter, and the two failure modes are symmetric:\n\n- **Leakage** — touching what the user did not name (a sharpen that re-grades color, an upscale that reframes, a style change that drifts a face, an outfit swap that drops an accessory, a background change that \"helpfully\" cleans up something unmentioned).\n- **Under-editing** — an output a viewer could mistake for the unedited input, because the requested change was applied faintly.\n\nPreservation locks **content, never edit strength**. Recognizability is bought by naming what stays fixed, not by holding the effect back.\n\n## What to Anchor, What to Decide\n\n**Anchor on the image.** Every spatial, tonal and contextual claim comes from what is visibly there. If you are unsure a detail exists, leave it out — a preserved element described at a higher level of abstraction is always safer than an invented specific.\n\n**Say what stays, without repainting it.** Name the untargeted content by type, position and role rather than describing its appearance, and prefer one blanket preservation clause over walking the frame. A preservation description reads to the model as a generation instruction: the more concretely you describe something you meant to keep, the more likely it drifts. Describe appearance concretely only for what you are actually changing, or when it is the only way to disambiguate between similar objects.\n\n**Identity is the hardest invariant.** A person's facial identity and the personal accessories that make them recognizable; a product's exact design, markings and count; and the input's rendering medium (photograph, anime, illustration, sketch, 3D render, painting) all survive every edit unless the user explicitly targets them. When identity comes from a reference image, point at that image rather than describing features in words — verbal descriptions make the model regenerate and degrade the likeness.\n\n**Resolve ambiguity, then commit.** Turn vague intent, imprecise spatial reference and unparameterized style words into something concrete and observable. Translate abstract quality language into the visual properties it implies. Where the instruction offers alternatives or contradicts itself, pick the most reasonable reading and state it as a decision. Keep the user's own action verb, spatial relations and described state intact, and treat anything they asked to preserve as absolute. Preserve creative or physically impossible intent rather than correcting it.\n\n**Only what was asked.** Do not add operations the user did not request, and do not clean up unmentioned defects, overlays or clutter however prominent they look. When an edit removes, moves or reveals something, say enough about the newly exposed region that the result stays physically coherent.\n\n**Text in the image is literal.** Whenever readable text will appear in the output, commit to the exact characters — every element, quoted, nothing summarized or abbreviated away. Text you cannot commit to should not be added at all. Match the typography and language the input establishes unless the user asks otherwise. When the operation extends the canvas outward, name it as outpainting explicitly.\n\n**Write it as an instruction.** Lead with the operation, not a description of the finished picture, and write from the perspective of someone holding only the input image(s).\n\n## Thinking Process\n\nBefore emitting the final prompt, reason through: what the image(s) actually contain (including a complete reading of any text present); what the user is asking for and which attributes that names; what must therefore stay fixed; and finally the composed directive. Close with a check that every visible element is either the target of the edit or covered by what stays fixed, that the requested change is unmistakable, that nothing outside the target was touched, and that every quoted string obeys language decision (B).\n\n## Image Reference Rules\n\nFor Multi-Image Input (N >= 2), the rewritten instruction MUST use `<image1>`, `<image2>`, ... to refer to each input image. Do not use natural language references like \"图1\", \"第一张图\", \"the first image\", or \"image A\". This tagging format is mandatory and non-negotiable. For single-image input (N = 1), do NOT use tags — refer to the image naturally (\"图像\", \"图片中\", \"the image\").\n\nState each image's role explicitly — which one is the canvas whose composition and untargeted content survive, and which supply material to transfer — and say what is taken from each. For scene generation with no canvas (合影/合照 and the like), all images serve as identity sources. Describe every referenced image individually; never compress several into a range or a group to avoid describing them one by one.\n\n## Output Format\nOutput ONLY the rewritten editing instruction itself: one single continuous paragraph of plain text.\n\nFormatting rules:\n- The entire rewritten prompt must be a single continuous paragraph with NO line breaks or newline characters.\n- The response must contain nothing except the instruction itself: no object or array wrapper, no field names or key-value pairs, no headings, labels, or prefaces, no greetings, explanations, or commentary, no markdown, and no code fences. Begin with the first word of the instruction and end with its last word.\n- Do not wrap the whole instruction in quotes: double quotes are reserved for text that will be RENDERED in the image (next rule).\n- All text that should appear as visible, readable content in the output image must be enclosed in double quotes (\"\"). Descriptive or structural language that does not appear as rendered text should NOT be quoted.\n- **Never include any resolution or aspect ratio information** (e.g., \"2:3\", \"16:9\", \"1920x1080\", \"2K\", \"4K\"). Output size is decided downstream, not by you.\n- Write it out in full — no ellipsis, no truncation.\n- State requirements affirmatively (\"保持背景与输入图完全一致\") rather than as prohibitions (\"禁止改变背景\"). Standard preservation phrasing \"保持/保留[X]不变\" is fine.\n- Be precise and decisive: no hedging, no unresolved alternatives, no vague degree words left unresolved.\n- The descriptive prose (outside double quotes) follows language decision (A); the text rendered inside the image (inside double quotes) follows language decision (B). Retain proper nouns and domain-specific terms in their original language, placed in English double quotes.\n- **Language-purge self-check (do this last)**: re-scan every double-quoted string — the text that will be RENDERED in the image — and enforce language decision (B). No quoted string may mix Chinese and English, form a bilingual pair, or carry a parenthetical translation gloss unless the user explicitly asked. Standardized units and user-given proper nouns may remain Latin.\n\nThe user's edit instruction to rewrite is:"
      },
      "class_type": "PrimitiveStringMultiline",
      "_meta": {
        "title": "Text (System Prompt)"
      }
    },
    "459:480": {
      "inputs": {
        "source": [
          "459:484",
          0
        ]
      },
      "class_type": "PreviewAny",
      "_meta": {
        "title": "预览任意"
      }
    },
    "459:484": {
      "inputs": {
        "switch": false,
        "on_false": "Replace costumes for the character",
        "on_true": [
          "459:500",
          0
        ]
      },
      "class_type": "ComfySwitchNode",
      "_meta": {
        "title": "切换"
      }
    },
    "459:485": {
      "inputs": {
        "images.image0": [
          "470",
          0
        ],
        "images.image1": [
          "475",
          0
        ]
      },
      "class_type": "BatchImagesNode",
      "_meta": {
        "title": "批量图像"
      }
    },
    "459:495": {
      "inputs": {
        "prompt": "",
        "negative_prompt": "",
        "resolution": 1024
      },
      "class_type": "TextEncodeQwenImage21",
      "_meta": {
        "title": "Text Encode Qwen Image 2.1"
      }
    },
    "459:500": {
      "inputs": {
        "prompt": "Replace costumes for the character",
        "max_length": 16256,
        "sampling_mode": "on",
        "sampling_mode.temperature": 1,
        "sampling_mode.top_k": 20,
        "sampling_mode.top_p": 0.95,
        "sampling_mode.min_p": 0.05,
        "sampling_mode.repetition_penalty": 1.05,
        "sampling_mode.seed": 1095460012924539,
        "sampling_mode.presence_penalty": 0,
        "thinking": true,
        "use_default_template": false,
        "mtp": "auto",
        "clip": [
          "459:477",
          0
        ],
        "image": [
          "459:485",
          0
        ]
      },
      "class_type": "TextGenerate",
      "_meta": {
        "title": "TextGenerate"
      }
    },
    "459:501": {
      "inputs": {
        "shift": 3.1000000000000005,
        "sampling": "flow",
        "model": [
          "459:469",
          0
        ]
      },
      "class_type": "ModelSamplingAuraFlow",
      "_meta": {
        "title": "采样算法（AuraFlow）"
      }
    }
  },
  qwenBackgroundRemoval:   {
    "461": {
      "inputs": {
        "filename_prefix": "Qwen_image_2.1",
        "format": "png",
        "format.bit_depth": "8-bit",
        "format.input_color_space": "sRGB",
        "images": [
          "459:457",
          0
        ]
      },
      "class_type": "SaveImageAdvanced",
      "_meta": {
        "title": "保存图像（高级）"
      }
    },
    "470": {
      "inputs": {
        "image": "angry_broccoli.png"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "加载图像"
      }
    },
    "472": {
      "inputs": {
        "compare_view": {
          "__value__": [
            "",
            ""
          ]
        },
        "image_a": [
          "470",
          0
        ],
        "image_b": [
          "461",
          0
        ]
      },
      "class_type": "ImageCompare",
      "_meta": {
        "title": "图像对比"
      }
    },
    "459:451": {
      "inputs": {
        "unet_name": "qwen-image-2.1-UC-Q8_0.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "459:453": {
      "inputs": {
        "clip_name": "qwen3vl_8b_int8_convrot.safetensors",
        "type": "qwen_image",
        "device": "default"
      },
      "class_type": "CLIPLoader",
      "_meta": {
        "title": "加载CLIP"
      }
    },
    "459:454": {
      "inputs": {
        "vae_name": "qwen_image_2.1_vae_bf16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "459:456": {
      "inputs": {
        "width": 1024,
        "height": 1024,
        "batch_size": 1
      },
      "class_type": "EmptyLatentImage",
      "_meta": {
        "title": "空Latent图像"
      }
    },
    "459:457": {
      "inputs": {
        "samples": [
          "459:458",
          0
        ],
        "vae": [
          "459:454",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "459:458": {
      "inputs": {
        "seed": 733114857276099,
        "steps": 25,
        "cfg": 2,
        "sampler_name": "euler",
        "scheduler": "simple",
        "denoise": 1,
        "model": [
          "459:477",
          0
        ],
        "positive": [
          "459:474",
          0
        ],
        "negative": [
          "459:474",
          1
        ],
        "latent_image": [
          "459:468",
          0
        ]
      },
      "class_type": "KSampler",
      "_meta": {
        "title": "K采样器"
      }
    },
    "459:468": {
      "inputs": {
        "switch": false,
        "on_false": [
          "459:474",
          2
        ],
        "on_true": [
          "459:456",
          0
        ]
      },
      "class_type": "ComfySwitchNode",
      "_meta": {
        "title": "切换"
      }
    },
    "459:469": {
      "inputs": {
        "device": "auto",
        "dtype": "default",
        "model": [
          "459:451",
          0
        ]
      },
      "class_type": "QwenImage21Cache",
      "_meta": {
        "title": "Qwen Image 2.1 Cache"
      }
    },
    "459:474": {
      "inputs": {
        "prompt": "Remove the background, and output a PNG image",
        "negative_prompt": "",
        "resolution": 0,
        "clip": [
          "459:453",
          0
        ],
        "images.image_1": [
          "470",
          0
        ],
        "vae": [
          "459:454",
          0
        ]
      },
      "class_type": "TextEncodeQwenImage21",
      "_meta": {
        "title": "Text Encode Qwen Image 2.1"
      }
    },
    "459:477": {
      "inputs": {
        "shift": 3.1000000000000005,
        "sampling": "flow",
        "model": [
          "459:469",
          0
        ]
      },
      "class_type": "ModelSamplingAuraFlow",
      "_meta": {
        "title": "采样算法（AuraFlow）"
      }
    }
  },
  h3T2v:   {
    "92": {
      "inputs": {
        "filename_prefix": "video/MiniMax_H3",
        "format": "auto",
        "format.codec": "auto",
        "codec": "auto",
        "video": [
          "128",
          0
        ]
      },
      "class_type": "SaveVideo",
      "_meta": {
        "title": "保存视频"
      }
    },
    "115": {
      "inputs": {
        "aspect_ratio": "16:9 (Widescreen)",
        "megapixels": 0.98,
        "multiple": 32
      },
      "class_type": "ResolutionSelector",
      "_meta": {
        "title": "分辨率选择器"
      }
    },
    "120": {
      "inputs": {
        "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "121": {
      "inputs": {
        "samples": [
          "135",
          0
        ],
        "vae": [
          "120",
          0
        ]
      },
      "class_type": "VAEDecodeAudio",
      "_meta": {
        "title": "VAE解码（音频）"
      }
    },
    "122": {
      "inputs": {
        "samples": [
          "135",
          0
        ],
        "vae": [
          "132",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "123": {
      "inputs": {
        "sampler_name": "res_multistep"
      },
      "class_type": "KSamplerSelect",
      "_meta": {
        "title": "K采样器选择"
      }
    },
    "124": {
      "inputs": {
        "scheduler": "simple",
        "steps": 20,
        "denoise": 1,
        "model": [
          "130",
          0
        ]
      },
      "class_type": "BasicScheduler",
      "_meta": {
        "title": "基本调度器"
      }
    },
    "125": {
      "inputs": {
        "noise": [
          "127",
          0
        ],
        "guider": [
          "126",
          0
        ],
        "sampler": [
          "123",
          0
        ],
        "sigmas": [
          "124",
          0
        ],
        "latent_image": [
          "136",
          0
        ]
      },
      "class_type": "SamplerCustomAdvanced",
      "_meta": {
        "title": "自定义采样器（高级）"
      }
    },
    "126": {
      "inputs": {
        "model": [
          "130",
          0
        ],
        "conditioning": [
          "129",
          0
        ]
      },
      "class_type": "BasicGuider",
      "_meta": {
        "title": "基本引导器"
      }
    },
    "127": {
      "inputs": {
        "noise_seed": 1104405517180391
      },
      "class_type": "RandomNoise",
      "_meta": {
        "title": "随机噪波"
      }
    },
    "128": {
      "inputs": {
        "fps": 24,
        "bit_depth": 8,
        "color_space": "sRGB",
        "codec": "none",
        "images": [
          "122",
          0
        ],
        "audio": [
          "121",
          0
        ]
      },
      "class_type": "CreateVideo",
      "_meta": {
        "title": "创建视频"
      }
    },
    "129": {
      "inputs": {
        "prompt": "integrated_multimodal_description: [Shot 1] Live-action, cinematic, a vaporwave title-sequence look with a pink and blue gradient palette, VHS tracking artifacts, Greek statue motifs, chrome palm trees, RGB chromatic aberration, and a lo-fi retro atmosphere. VHS static opens the frame and the title \"GGUF\" appears with an RGB split and a slight horizontal jitter while the camera holds a static shot. [Shot 2] At 00:01.000, the shot cuts to a close-up of a Greek plaster bust against a pink-purple gradient sky with a pixelated sun; the camera pushes in with small amplitude at slow speed. [Shot 3] At 00:02.500, the shot cuts to a medium shot of clean \"STARRING\" credits appearing in glowing neon lettering beside chrome palm trees, listing the names \"LATENT\" and \"CONTROLNET\" in sequence. [Shot 4] At 00:04.000, the shot cuts to a final title card reading \"DIRECTED BY COMFYUI\"; one VHS tracking glitch passes across the frame before the picture settles into stable playback for the final second.\n\noverall_soundscape: VHS tape hiss and a faint electronic hum run continuously through the video; the opening static burst crackles loudly at the start and fades as the first title lands, with occasional tape wobble underneath.\n\nnon_diegetic_music: A lo-fi vaporwave score at a slow tempo with a soft steady drum-machine beat and a warm bass line, joined by a tape-noise sample at 2.5 seconds; the melody gradually fades out during the final second.",
        "width": [
          "115",
          0
        ],
        "height": [
          "115",
          1
        ],
        "length": [
          "133",
          1
        ],
        "clip": [
          "131",
          0
        ],
        "vae": [
          "132",
          0
        ]
      },
      "class_type": "MiniMaxH3ImageToVideo",
      "_meta": {
        "title": "MiniMax H3 图像转视频"
      }
    },
    "130": {
      "inputs": {
        "unet_name": "minimax_h3_fl2va_pruned-Q4_K_M.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "131": {
      "inputs": {
        "clip_name": "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
        "type": "boogu",
        "projection": "mmh3-8b-ClipProj-v3.1.safetensors"
      },
      "class_type": "CCTechClipProjLoader",
      "_meta": {
        "title": "Text Encoder 8B (boogu)"
      }
    },
    "132": {
      "inputs": {
        "vae_name": "minimax_h3_video_vae_fp16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "133": {
      "inputs": {
        "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
        "values.a": [
          "134",
          0
        ]
      },
      "class_type": "ComfyMathExpression",
      "_meta": {
        "title": "数学表达式"
      }
    },
    "134": {
      "inputs": {
        "value": 5
      },
      "class_type": "PrimitiveFloat",
      "_meta": {
        "title": "Float (duration)"
      }
    },
    "135": {
      "inputs": {
        "latent": [
          "125",
          0
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    },
    "136": {
      "inputs": {
        "latent": [
          "129",
          1
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    }
  },
  h3I2v:   {
    "92": {
      "inputs": {
        "filename_prefix": "video/MiniMax_H3",
        "format": "auto",
        "format.codec": "auto",
        "codec": "auto",
        "video": [
          "132",
          0
        ]
      },
      "class_type": "SaveVideo",
      "_meta": {
        "title": "保存视频"
      }
    },
    "114": {
      "inputs": {
        "image": "bg-cerritos-exterior-01.jpg"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "First Frame"
      }
    },
    "115": {
      "inputs": {
        "aspect_ratio": "16:9 (Widescreen)",
        "megapixels": 0.5,
        "multiple": 32
      },
      "class_type": "ResolutionSelector",
      "_meta": {
        "title": "分辨率选择器"
      }
    },
    "123": {
      "inputs": {
        "vae_name": "minimax_h3_video_vae_fp16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "124": {
      "inputs": {
        "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "125": {
      "inputs": {
        "samples": [
          "145",
          0
        ],
        "vae": [
          "124",
          0
        ]
      },
      "class_type": "VAEDecodeAudio",
      "_meta": {
        "title": "VAE解码（音频）"
      }
    },
    "126": {
      "inputs": {
        "samples": [
          "145",
          0
        ],
        "vae": [
          "123",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "127": {
      "inputs": {
        "sampler_name": "res_multistep"
      },
      "class_type": "KSamplerSelect",
      "_meta": {
        "title": "K采样器选择"
      }
    },
    "128": {
      "inputs": {
        "scheduler": "simple",
        "steps": 20,
        "denoise": 1,
        "model": [
          "136",
          0
        ]
      },
      "class_type": "BasicScheduler",
      "_meta": {
        "title": "基本调度器"
      }
    },
    "129": {
      "inputs": {
        "noise": [
          "131",
          0
        ],
        "guider": [
          "130",
          0
        ],
        "sampler": [
          "127",
          0
        ],
        "sigmas": [
          "128",
          0
        ],
        "latent_image": [
          "146",
          0
        ]
      },
      "class_type": "SamplerCustomAdvanced",
      "_meta": {
        "title": "自定义采样器（高级）"
      }
    },
    "130": {
      "inputs": {
        "model": [
          "136",
          0
        ],
        "conditioning": [
          "133",
          0
        ]
      },
      "class_type": "BasicGuider",
      "_meta": {
        "title": "基本引导器"
      }
    },
    "131": {
      "inputs": {
        "noise_seed": 377090417907782
      },
      "class_type": "RandomNoise",
      "_meta": {
        "title": "随机噪波"
      }
    },
    "132": {
      "inputs": {
        "fps": 24,
        "bit_depth": 8,
        "color_space": "sRGB",
        "codec": "none",
        "images": [
          "126",
          0
        ],
        "audio": [
          "125",
          0
        ]
      },
      "class_type": "CreateVideo",
      "_meta": {
        "title": "创建视频"
      }
    },
    "133": {
      "inputs": {
        "prompt": "How the reference pictures align with the target video - Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 5.00-second mark of the target video.\n\nintegrated_multimodal_description: [Shot 1] 3D-animated, cinematic sci-fi style, the starship Cerritors begins in the position and framing established by Picture 1, orbiting over a planet with its engines glowing. The camera pans right following the animated starship as it flies across deep space; the nacelles gradually glow brighter, the ship accelerates forward at incredibly fast warp speed with a brief flash and stretched light trails, then eases as a title card displaying the text \"Minimax H3\" with the secondary title \"GGUF U16G\" settles into the frame; the sequence ends in the composition established by Picture 2 at the 5.00-second mark.\n\noverall_soundscape: A low deep-space rumble continues underneath, with a rising engine hum that swells during the warp acceleration and a brief electronic flash sound at the burst.\n\nnon_diegetic_music: An orchestral dramatic sci-fi theme at a moderate tempo with bold brass and strings, rising in intensity during the warp jump and cutting off cleanly as the title card appears.",
        "width": [
          "115",
          0
        ],
        "height": [
          "115",
          1
        ],
        "length": [
          "134",
          1
        ],
        "clip": [
          "137",
          0
        ],
        "vae": [
          "123",
          0
        ],
        "first_frame": [
          "144",
          0
        ],
        "last_frame": [
          "142",
          0
        ]
      },
      "class_type": "MiniMaxH3ImageToVideo",
      "_meta": {
        "title": "MiniMax H3 图像转视频"
      }
    },
    "134": {
      "inputs": {
        "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
        "values.a": [
          "135",
          0
        ]
      },
      "class_type": "ComfyMathExpression",
      "_meta": {
        "title": "数学表达式"
      }
    },
    "135": {
      "inputs": {
        "value": 5
      },
      "class_type": "PrimitiveFloat",
      "_meta": {
        "title": "Float (duration)"
      }
    },
    "136": {
      "inputs": {
        "unet_name": "minimax_h3_fl2va_pruned-Q4_K_M.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "137": {
      "inputs": {
        "clip_name": "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
        "type": "boogu",
        "projection": "mmh3-8b-ClipProj-v3.1.safetensors"
      },
      "class_type": "CCTechClipProjLoader",
      "_meta": {
        "title": "Text Encoder 8B (boogu)"
      }
    },
    "141": {
      "inputs": {
        "image": "bg-cerritos-exterior-01.jpg"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "Last Frame"
      }
    },
    "142": {
      "inputs": {
        "resize_type": "scale dimensions",
        "resize_type.width": [
          "115",
          0
        ],
        "resize_type.height": [
          "115",
          1
        ],
        "resize_type.crop": "center",
        "scale_method": "nearest-exact",
        "input": [
          "141",
          0
        ]
      },
      "class_type": "ResizeImageMaskNode",
      "_meta": {
        "title": "调整图像/掩码大小"
      }
    },
    "144": {
      "inputs": {
        "resize_type": "scale dimensions",
        "resize_type.width": [
          "115",
          0
        ],
        "resize_type.height": [
          "115",
          1
        ],
        "resize_type.crop": "center",
        "scale_method": "nearest-exact",
        "input": [
          "114",
          0
        ]
      },
      "class_type": "ResizeImageMaskNode",
      "_meta": {
        "title": "调整图像/掩码大小"
      }
    },
    "145": {
      "inputs": {
        "latent": [
          "129",
          0
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    },
    "146": {
      "inputs": {
        "latent": [
          "133",
          1
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    }
  },
  h3Ref2v:   {
    "92": {
      "inputs": {
        "filename_prefix": "video/MiniMax_H3",
        "format": "auto",
        "format.codec": "auto",
        "codec": "auto",
        "video": [
          "132",
          0
        ]
      },
      "class_type": "SaveVideo",
      "_meta": {
        "title": "保存视频"
      }
    },
    "115": {
      "inputs": {
        "aspect_ratio": "9:16 (Portrait Widescreen)",
        "megapixels": 0.5,
        "multiple": 32
      },
      "class_type": "ResolutionSelector",
      "_meta": {
        "title": "分辨率选择器"
      }
    },
    "123": {
      "inputs": {
        "vae_name": "minimax_h3_video_vae_fp16.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "124": {
      "inputs": {
        "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
      },
      "class_type": "VAELoader",
      "_meta": {
        "title": "加载VAE"
      }
    },
    "125": {
      "inputs": {
        "samples": [
          "157",
          0
        ],
        "vae": [
          "124",
          0
        ]
      },
      "class_type": "VAEDecodeAudio",
      "_meta": {
        "title": "VAE解码（音频）"
      }
    },
    "126": {
      "inputs": {
        "samples": [
          "157",
          0
        ],
        "vae": [
          "123",
          0
        ]
      },
      "class_type": "VAEDecode",
      "_meta": {
        "title": "VAE解码"
      }
    },
    "127": {
      "inputs": {
        "sampler_name": "er_sde"
      },
      "class_type": "KSamplerSelect",
      "_meta": {
        "title": "K采样器选择"
      }
    },
    "128": {
      "inputs": {
        "scheduler": "simple",
        "steps": 20,
        "denoise": 1,
        "model": [
          "136",
          0
        ]
      },
      "class_type": "BasicScheduler",
      "_meta": {
        "title": "基本调度器"
      }
    },
    "129": {
      "inputs": {
        "noise": [
          "131",
          0
        ],
        "guider": [
          "130",
          0
        ],
        "sampler": [
          "127",
          0
        ],
        "sigmas": [
          "128",
          0
        ],
        "latent_image": [
          "158",
          0
        ]
      },
      "class_type": "SamplerCustomAdvanced",
      "_meta": {
        "title": "自定义采样器（高级）"
      }
    },
    "130": {
      "inputs": {
        "model": [
          "136",
          0
        ],
        "conditioning": [
          "145",
          0
        ]
      },
      "class_type": "BasicGuider",
      "_meta": {
        "title": "基本引导器"
      }
    },
    "131": {
      "inputs": {
        "noise_seed": 258027117257533
      },
      "class_type": "RandomNoise",
      "_meta": {
        "title": "随机噪波"
      }
    },
    "132": {
      "inputs": {
        "fps": 24,
        "bit_depth": 8,
        "color_space": "sRGB",
        "codec": "none",
        "images": [
          "126",
          0
        ],
        "audio": [
          "125",
          0
        ]
      },
      "class_type": "CreateVideo",
      "_meta": {
        "title": "创建视频"
      }
    },
    "134": {
      "inputs": {
        "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
        "values.a": [
          "135",
          0
        ]
      },
      "class_type": "ComfyMathExpression",
      "_meta": {
        "title": "数学表达式"
      }
    },
    "135": {
      "inputs": {
        "value": 5
      },
      "class_type": "PrimitiveFloat",
      "_meta": {
        "title": "Float (duration)"
      }
    },
    "136": {
      "inputs": {
        "unet_name": "minimax_h3_ref2va_pruned-Q4_K_M.gguf"
      },
      "class_type": "UnetLoaderGGUF",
      "_meta": {
        "title": "UNET Loader (GGUF) ⚡"
      }
    },
    "137": {
      "inputs": {
        "clip_name": "qwen3-vl-8b-heretic-1.3.0_fp8_e4m3fn.safetensors",
        "type": "boogu",
        "projection": "mmh3-8b-ClipProj-v3.1.safetensors"
      },
      "class_type": "CCTechClipProjLoader",
      "_meta": {
        "title": "Text Encoder 8B (boogu)"
      }
    },
    "145": {
      "inputs": {
        "prompt": "subject_definitions:\n<Subject 1> is the baby in <Picture 1>, with rosy cheeks, wispy hair, and a striped onesie, seated in a shopping cart. <Subject 2> is the shopping-cart environment in <Picture 1>, including the silver metal frame, seat, and basket. <Subject 3> is the glossy red apple held by the baby, from <Picture 1> and <Video 1>. <Audio 1> is the exaggerated \"nom nom\" chewing audio from the reference audio, used as the delivery reference for the baby's chewing sounds.\n\nsummary:\n[reference generation + audio reference] The target video shows <Subject 1> seated in <Subject 2> chewing <Subject 3> with exaggerated \"nom nom\" sounds following <Audio 1>, ending with the titles \"MiniMax H3 Ref2VA\" and \"GGUF Q8_CR\" displayed on screen.\n\nretention_analysis:\n<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - the baby's appearance, clothing, and seated posture from <Picture 1> are retained.\n<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the shopping cart's frame, seat, and basket are retained.\n<Subject 3> (appears in [Shot 1]): fully_preserved - the red apple and its size relative to the baby's hands are retained.\n<Audio 1>: reference - the chewing sounds follow <Audio 1>'s exaggerated rhythm and delivery without copying the original signal.\n\ndetailed_description:\nThe target video is in a bright, realistic, slightly oversized 3D-animated family-film style with soft lighting.\n[Shot 1] The scene opens in a softly lit supermarket aisle with colorful product packaging blurred in the background, showing <Subject 2>, the silver shopping cart, from a medium shot. <Subject 1>, the baby from <Picture 1> with rosy cheeks, wispy hair, and a striped onesie, sits in the cart seat holding <Subject 3>, a glossy red apple, in both hands. The baby raises the apple, takes a chunky bite, and chews with comically over-expressive cheek and jaw movements, each bite landing with an exaggerated \"nom nom\" sound following the rhythm of <Audio 1>; crumbs collect on the lips and the apple juice shines under the store lights. The camera holds the composition from <Picture 1> and slowly pushes in with small amplitude at slow speed, keeping the baby centered. [Shot 2] At 00:03.500, the shot cuts to a slightly wider angle of the baby in the cart still chewing, as a clean title card \"MiniMax H3 Ref2VA\" fades in across the top of the frame with the secondary title \"GGUF Q8_CR\" below it; the camera holds a static shot while the titles settle, and the baby swallows the final bite as the video ends on the framing of <Picture 1>.\n\noverall_soundscape: Soft supermarket room tone continues throughout, with the wet exaggerated chewing sounds and light rustling of the apple in the baby's hands.\n\nnon_diegetic_music: N/A",
        "width": [
          "115",
          0
        ],
        "height": [
          "115",
          1
        ],
        "length": [
          "134",
          1
        ],
        "ref_image_size": "match",
        "clip": [
          "137",
          0
        ],
        "vae": [
          "123",
          0
        ],
        "audio_vae": [
          "124",
          0
        ],
        "ref_images.ref_image_0": [
          "149",
          0
        ],
        "ref_videos.ref_video_0": [
          "152",
          0
        ],
        "ref_video_audios.ref_video_audio_0": [
          "152",
          1
        ],
        "ref_audios.ref_audio_0": [
          "153",
          0
        ]
      },
      "class_type": "MiniMaxH3ReferenceToVideo",
      "_meta": {
        "title": "MiniMax H3 参考转视频"
      }
    },
    "149": {
      "inputs": {
        "image": "326498a7-9cab-4b04-a1fa-29abb2c4521b.png"
      },
      "class_type": "LoadImage",
      "_meta": {
        "title": "Reference Image 1"
      }
    },
    "152": {
      "inputs": {
        "video": [
          "156",
          0
        ]
      },
      "class_type": "GetVideoComponents",
      "_meta": {
        "title": "获取视频元素"
      }
    },
    "153": {
      "inputs": {
        "audio": "tf2-heavy-om-nom-nom-sound-effect.mp3"
      },
      "class_type": "LoadAudio",
      "_meta": {
        "title": "加载音频"
      }
    },
    "156": {
      "inputs": {
        "file": "17IV64UE.mp4",
        "video-preview": ""
      },
      "class_type": "LoadVideo",
      "_meta": {
        "title": "Reference Video 1"
      }
    },
    "157": {
      "inputs": {
        "latent": [
          "129",
          0
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    },
    "158": {
      "inputs": {
        "latent": [
          "145",
          1
        ]
      },
      "class_type": "ForceUnloadBeforeDecode",
      "_meta": {
        "title": "Force Unload Before Decode"
      }
    }
  },
};

let uploadCounter = 0;

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function isLink(value) {
  return Array.isArray(value) && value.length === 2 && typeof value[0] === "string" && typeof value[1] === "number";
}

function endpoint(context, path) {
  const configured = String(context.config?.baseUrl ?? "").trim();
  return `${(configured || "http://127.0.0.1:8188").replace(/\/+$/, "")}${path}`;
}

function delay(signal, ms) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason ?? new Error("已取消"));
      return;
    }
    const abort = () => {
      clearTimeout(timer);
      reject(signal?.reason ?? new Error("已取消"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", abort, { once: true });
  });
}

function randomSeed() {
  return Math.floor(Math.random() * Number.MAX_SAFE_INTEGER);
}

function durationSeconds(value, fallback) {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function megapixelsFrom(label, fallback) {
  const match = typeof label === "string" ? /^\s*([\d.]+)\s*MP\s*$/i.exec(label) : null;
  const value = match ? Number.parseFloat(match[1]) : NaN;
  return Number.isFinite(value) && value >= 0.1 && value <= 4 ? value : fallback;
}

function applyRatio(graph, nodeId, ratio) {
  if (ratio && ratioLabels[ratio]) graph[nodeId].inputs.aspect_ratio = ratioLabels[ratio];
}

function dropAudio(graph, createVideoId) {
  delete graph[createVideoId].inputs.audio;
}

// 只保留从输出节点可达的节点，避免可选输入缺席时留下悬空连线。
function prune(graph, outputIds) {
  const keep = new Set();
  const pending = [...outputIds];
  while (pending.length) {
    const id = pending.pop();
    if (keep.has(id) || !graph[id]) continue;
    keep.add(id);
    for (const value of Object.values(graph[id].inputs ?? {})) if (isLink(value)) pending.push(value[0]);
  }
  for (const id of Object.keys(graph)) if (!keep.has(id)) delete graph[id];
  for (const node of Object.values(graph)) {
    for (const [key, value] of Object.entries(node.inputs ?? {})) if (isLink(value) && !graph[value[0]]) delete node.inputs[key];
  }
}

function extensionFor(input) {
  const mimeType = String(input.mimeType ?? "").split(";")[0].trim().toLowerCase();
  if (mimeExtensions[mimeType]) return mimeExtensions[mimeType];
  const match = /\.([a-z0-9]+)$/i.exec(String(input.name ?? ""));
  return match ? `.${match[1].toLowerCase()}` : ".bin";
}

async function readBytes(context, input) {
  if (input.type === "base64") return new Uint8Array(Buffer.from(input.data.replace(/^data:[^;]+;base64,/, ""), "base64"));
  if (input.type === "binary") return input.data;
  const response = await context.tool.fetch(input.url, { signal: context.signal });
  if (!response.ok) throw new Error(`读取参考媒体失败（HTTP ${response.status}）`);
  return new Uint8Array(await response.arrayBuffer());
}

function buildMultipart(parts, boundary) {
  const encoder = new TextEncoder();
  const chunks = [];
  for (const part of parts) {
    let header = `--${boundary}\r\nContent-Disposition: form-data; name="${part.name}"`;
    if (part.filename) header += `; filename="${part.filename}"`;
    header += "\r\n";
    if (part.contentType) header += `Content-Type: ${part.contentType}\r\n`;
    header += "\r\n";
    chunks.push(encoder.encode(header));
    chunks.push(part.data ?? encoder.encode(part.value ?? ""));
    chunks.push(encoder.encode("\r\n"));
  }
  chunks.push(encoder.encode(`--${boundary}--\r\n`));
  const body = new Uint8Array(chunks.reduce((size, chunk) => size + chunk.byteLength, 0));
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

// ComfyUI 只有 /upload/image，但它按原始字节写盘，视频与音频同样可以经此上传。
async function upload(context, input, mediaType) {
  const bytes = await readBytes(context, input);
  const filename = `toonflow_${Date.now()}_${++uploadCounter}${extensionFor(input)}`;
  const boundary = `----toonflow${Math.random().toString(16).slice(2, 12)}`;
  const body = buildMultipart([
    { name: "image", filename, contentType: input.mimeType, data: bytes },
    { name: "type", value: "input" },
    { name: "subfolder", value: "toonflow" },
    { name: "overwrite", value: "true" },
  ], boundary);
  const response = await context.tool.fetch(endpoint(context, "/upload/image"), {
    method: "POST",
    headers: { "content-type": `multipart/form-data; boundary=${boundary}` },
    body,
    signal: context.signal,
  });
  if (!response.ok) throw new Error(`上传参考${mediaType}失败（HTTP ${response.status}）：${await readError(context, response)}`);
  const uploaded = await response.json();
  if (typeof uploaded?.name !== "string" || !uploaded.name) throw new Error("ComfyUI 上传接口未返回文件名");
  return uploaded.subfolder ? `${uploaded.subfolder}/${uploaded.name}` : uploaded.name;
}

async function readError(context, response) {
  const text = await response.text().catch(() => "");
  const parts = [];
  try {
    const nodeErrors = JSON.parse(text)?.node_errors;
    if (nodeErrors && typeof nodeErrors === "object") {
      for (const [nodeId, info] of Object.entries(nodeErrors)) {
        for (const item of Array.isArray(info?.errors) ? info.errors : []) parts.push(`${nodeId}: ${item?.message ?? item?.details ?? ""}`);
      }
    }
  } catch {}
  return parts.filter(Boolean).join("; ") || context.tool.errorMessage(text) || text.slice(0, 400) || "无错误详情";
}

function describeMessages(messages) {
  const parts = [];
  for (const item of Array.isArray(messages) ? messages : []) {
    const data = Array.isArray(item) ? item[1] : undefined;
    if (typeof data === "string") parts.push(data);
    else if (data && typeof data === "object") {
      for (const key of ["exception_message", "message", "error", "traceback"]) if (typeof data[key] === "string" && data[key]) parts.push(data[key]);
      if (data.node_type) parts.push(`节点 ${data.node_type}`);
    }
  }
  return [...new Set(parts)].join(" / ").slice(0, 1200) || "未知错误";
}

function findResultFile(outputs, nodeId) {
  const nodes = outputs && typeof outputs === "object" ? outputs : {};
  for (const key of [nodeId, ...Object.keys(nodes)]) {
    const node = nodes[key];
    if (!node || typeof node !== "object") continue;
    for (const value of Object.values(node)) {
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item && typeof item === "object" && typeof item.filename === "string") return item;
      }
    }
  }
  return undefined;
}

async function runWorkflow(context, graph, outputNodeId, timeoutMs) {
  const response = await context.tool.fetch(endpoint(context, "/prompt"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ prompt: graph }),
    signal: context.signal,
  });
  if (!response.ok) throw new Error(`提交 ComfyUI 任务失败（HTTP ${response.status}）：${await readError(context, response)}`);
  const created = await response.json();
  const promptId = created?.prompt_id;
  if (typeof promptId !== "string" || !promptId) throw new Error(`ComfyUI 未接受任务：${JSON.stringify(created).slice(0, 800)}`);
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    await delay(context.signal, 1200);
    if (Date.now() > deadline) throw new Error("等待 ComfyUI 生成结果超时");
    const historyResponse = await context.tool.fetch(endpoint(context, `/history/${promptId}`), { signal: context.signal });
    if (!historyResponse.ok) continue;
    const history = await historyResponse.json();
    const entry = history?.[promptId];
    if (!entry) continue;
    const status = String(entry?.status?.status_str ?? "");
    if (status === "error") throw new Error(`ComfyUI 执行失败：${describeMessages(entry.status?.messages)}`);
    if (status !== "success") continue;
    const file = findResultFile(entry.outputs, outputNodeId);
    if (!file) throw new Error("ComfyUI 执行完成但未返回结果文件");
    return file;
  }
}

function resultAsset(context, file, mediaType) {
  const params = new URLSearchParams();
  params.set("filename", file.filename);
  if (file.subfolder) params.set("subfolder", file.subfolder);
  params.set("type", file.type ?? "output");
  const query = params.toString();
  const extension = /\.([a-z0-9]+)$/i.exec(file.filename)?.[1]?.toLowerCase() ?? "";
  const mimeType = Object.entries(mimeExtensions).find(([, ext]) => ext === `.${extension}`)?.[0]
    ?? (mediaType === "image" ? "image/png" : mediaType === "video" ? "video/mp4" : "audio/wav");
  return { type: "url", url: `${endpoint(context, "/view")}?${query}`, mimeType, mediaType };
}

async function generateQwenT2i(context, request) {
  if (request.images?.length) throw new Error("文生图模型不接受参考图，请改用「Qwen Image 2.1 图像编辑」");
  const graph = clone(templates.qwenT2i);
  graph["459:474"].inputs.on_false = request.prompt;
  applyRatio(graph, "13", request.ratio);
  graph["13"].inputs.megapixels = megapixelsFrom(request.size, graph["13"].inputs.megapixels);
  graph["459:458"].inputs.seed = randomSeed();
  return [resultAsset(context, await runWorkflow(context, graph, "461", imageTimeout), "image")];
}

async function generateQwenEdit(context, request) {
  const images = request.images ?? [];
  if (!images.length) throw new Error("图像编辑至少需要 1 张参考图");
  if (images.length > 16) throw new Error("图像编辑最多支持 16 张参考图");
  const graph = clone(templates.qwenImageEdit);
  graph["459:484"].inputs.on_false = request.prompt;
  graph["459:458"].inputs.seed = randomSeed();
  graph["470"].inputs.image = await upload(context, images[0], "图片");
  if (images[1]) {
    graph["475"].inputs.image = await upload(context, images[1], "图片");
  } else {
    // 单图时不接第二张参考，同时断开只服务于生成增强的分支。
    delete graph["459:474"].inputs["images.image_2"];
    delete graph["459:484"].inputs.on_true;
  }
  for (let index = 2; index < images.length; index++) {
    const nodeId = `toonflow_image_${index + 1}`;
    graph[nodeId] = { class_type: "LoadImage", inputs: { image: await upload(context, images[index], "图片") } };
    graph["459:474"].inputs[`images.image_${index + 1}`] = [nodeId, 0];
  }
  prune(graph, ["461"]);
  return [resultAsset(context, await runWorkflow(context, graph, "461", imageTimeout), "image")];
}

async function generateQwenBackgroundRemoval(context, request) {
  const images = request.images ?? [];
  if (!images.length) throw new Error("背景移除需要 1 张图片");
  if (images.length > 1) throw new Error("背景移除只支持 1 张图片");
  const graph = clone(templates.qwenBackgroundRemoval);
  graph["459:474"].inputs.prompt = request.prompt;
  graph["459:458"].inputs.seed = randomSeed();
  graph["470"].inputs.image = await upload(context, images[0], "图片");
  prune(graph, ["461"]);
  return [resultAsset(context, await runWorkflow(context, graph, "461", imageTimeout), "image")];
}

async function generateH3T2v(context, request) {
  const graph = clone(templates.h3T2v);
  graph["129"].inputs.prompt = request.prompt;
  graph["134"].inputs.value = durationSeconds(request.duration, graph["134"].inputs.value);
  graph["127"].inputs.noise_seed = randomSeed();
  applyRatio(graph, "115", request.ratio);
  graph["115"].inputs.megapixels = megapixelsFrom(request.resolution, graph["115"].inputs.megapixels);
  if (request.generateAudio === false) dropAudio(graph, "128");
  prune(graph, ["92"]);
  return [resultAsset(context, await runWorkflow(context, graph, "92", videoTimeout), "video")];
}

async function generateH3I2v(context, request) {
  const firstFrame = request.firstFrame ?? request.images?.[0];
  const lastFrame = request.lastFrame ?? request.images?.[1];
  if (!firstFrame && !lastFrame) throw new Error("图生视频至少需要首帧或尾帧图片");
  const graph = clone(templates.h3I2v);
  graph["133"].inputs.prompt = request.prompt;
  graph["135"].inputs.value = durationSeconds(request.duration, graph["135"].inputs.value);
  graph["131"].inputs.noise_seed = randomSeed();
  applyRatio(graph, "115", request.ratio);
  graph["115"].inputs.megapixels = megapixelsFrom(request.resolution, graph["115"].inputs.megapixels);
  if (firstFrame) graph["114"].inputs.image = await upload(context, firstFrame, "图片");
  else delete graph["133"].inputs.first_frame;
  if (lastFrame) graph["141"].inputs.image = await upload(context, lastFrame, "图片");
  else delete graph["133"].inputs.last_frame;
  if (request.generateAudio === false) dropAudio(graph, "132");
  prune(graph, ["92"]);
  return [resultAsset(context, await runWorkflow(context, graph, "92", videoTimeout), "video")];
}

async function generateH3Ref2v(context, request) {
  const images = request.images ?? [];
  const videos = request.videos ?? [];
  const audios = request.audios ?? [];
  if (!images.length && !videos.length && !audios.length) throw new Error("参考生视频至少需要 1 个参考素材");
  const graph = clone(templates.h3Ref2v);
  graph["145"].inputs.prompt = request.prompt;
  graph["135"].inputs.value = durationSeconds(request.duration, graph["135"].inputs.value);
  graph["131"].inputs.noise_seed = randomSeed();
  applyRatio(graph, "115", request.ratio);
  graph["115"].inputs.megapixels = megapixelsFrom(request.resolution, graph["115"].inputs.megapixels);
  if (images[0]) graph["149"].inputs.image = await upload(context, images[0], "图片");
  else delete graph["145"].inputs["ref_images.ref_image_0"];
  if (videos[0]) graph["156"].inputs.file = await upload(context, videos[0], "视频");
  else {
    delete graph["145"].inputs["ref_videos.ref_video_0"];
    delete graph["145"].inputs["ref_video_audios.ref_video_audio_0"];
  }
  if (audios[0]) graph["153"].inputs.audio = await upload(context, audios[0], "音频");
  else delete graph["145"].inputs["ref_audios.ref_audio_0"];
  if (request.generateAudio === false) dropAudio(graph, "132");
  prune(graph, ["92"]);
  return [resultAsset(context, await runWorkflow(context, graph, "92", videoTimeout), "video")];
}

export default {
  id: "comfyui",
  label: "本地 ComfyUI",
  version,
  readme: "直接调用本机 ComfyUI 的 API 工作流生成图片与视频，默认地址 http://127.0.0.1:8188。\n\n- 使用前请先启动 ComfyUI，并确认已安装工作流所需的模型（Qwen Image 2.1 GGUF、MiniMax H3 及对应 VAE / CLIP / CLIP Proj）。\n- 参考素材会自动上传到 ComfyUI 的 input/toonflow 目录。\n- 每次生成使用随机种子；比例对应工作流的分辨率选择器，视频时长与分辨率由画布节点选择。\n- 取消生成只会停止等待，不会中断 ComfyUI 中已排队的任务。",
  rules,
  models: [
    {
      id: "qwen-image-t2i",
      label: "Qwen Image 2.1 文生图",
      type: "image",
      mode: ["text"],
      imageSizes: ["0.5MP", "1MP", "2MP"],
      imageRatios: ["1:1", "2:3", "3:2", "3:4", "4:3", "9:16", "16:9", "21:9"],
    },
    {
      id: "qwen-image-edit",
      label: "Qwen Image 2.1 图像编辑",
      type: "image",
      mode: ["singleImage", "multiReference"],
    },
    {
      id: "qwen-image-background-removal",
      label: "Qwen Image 2.1 背景移除",
      type: "image",
      mode: ["singleImage"],
    },
    {
      id: "minimax-h3-t2v",
      label: "MiniMax H3 文生视频",
      type: "video",
      mode: ["text"],
      audio: "optional",
      durationResolutionMap: [{ duration: [5, 8, 10], resolution: ["0.98MP"] }],
    },
    {
      id: "minimax-h3-i2v",
      label: "MiniMax H3 图生视频",
      type: "video",
      mode: ["singleImage", "startEndRequired", "endFrameOptional", "startFrameOptional"],
      audio: "optional",
      durationResolutionMap: [{ duration: [5, 8, 10], resolution: ["0.5MP"] }],
    },
    {
      id: "minimax-h3-ref2v",
      label: "MiniMax H3 参考生视频",
      type: "video",
      mode: [["imageReference:1", "videoReference:1", "audioReference:1"]],
      audio: "optional",
      durationResolutionMap: [{ duration: [5, 8, 10], resolution: ["0.5MP"] }],
    },
  ],
  generateImage(request) {
    if (request.model === "qwen-image-t2i") return generateQwenT2i(this, request);
    if (request.model === "qwen-image-edit") return generateQwenEdit(this, request);
    if (request.model === "qwen-image-background-removal") return generateQwenBackgroundRemoval(this, request);
    throw new Error(`不支持的图片模型：${request.model}`);
  },
  generateVideo(request) {
    if (request.model === "minimax-h3-t2v") return generateH3T2v(this, request);
    if (request.model === "minimax-h3-i2v") return generateH3I2v(this, request);
    if (request.model === "minimax-h3-ref2v") return generateH3Ref2v(this, request);
    throw new Error(`不支持的视频模型：${request.model}`);
  },
};
