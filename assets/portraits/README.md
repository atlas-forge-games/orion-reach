# Orion Reach — race portraits v1

Eleven race portraits and one Observer portrait generated with the built-in image-generation tool.
The game uses these portraits on the New Game race cards and the Diplomacy
screen, including your own empire's profile. Extract updates into the repository
root to place the files under assets/portraits/.

| Race | Portrait file |
| --- | --- |
| Terrans | terran-v1.png |
| Kharuun | kharuun-v1.png |
| Aelari | aelari-v1.png |
| Lithar | lithar-v1.png |
| Varkesh | varkesh-v1.png |
| Wanderers | wanderers-v1.png |
| Xenonflora | xenonflora-v1.png |
| Nexus | nexus-v1.png |
| Aetheri | aetheri-v1.png |
| The Concord | concord-v1.png |
| The Remnant | remnant-v1.png |
| The Observer (spectator mode) | observer-v1.png |

Each file is the unmodified generated PNG, with an opaque dark background.
The renderer preserves their aspect ratio and caches loaded and scaled images.
Missing or unreadable images fall back to the matching procedural race emblem.
To replace a portrait, keep its filename and restart the game. The filename stem
before `-v1` is the stable race ID. The eight additions use the selected final
portraits: Lithar are irregular living stones, Varkesh are crablike raiders,
Wanderers are mothlike navigators, Xenonflora are branching plant organisms,
Nexus are linked floating machines, Aetheri are loops of luminous energy,
the Concord are symbiotic organisms, and the Remnant is a hooded humanoid
survivor with a proud, patient, melancholy expression. Earlier portrait drafts
are not included in the game.

## Generation prompts

The Observer is an original pale, bald, watchful character in a dark suit and
fedora, inspired by the quiet, mysterious mood of the Observers in *Fringe*.
It is not a portrait of a particular actor. The square PNG is preserved exactly
as generated. Its complete prompt is in `observer-generation-prompt.txt`.
The Observer is a setup identity only; computer rivals never use this portrait
or race. If the PNG is missing, an eye emblem remains available.

### terran

Use case: stylized-concept.
Asset type: a standalone square character portrait for the diplomacy screen of Orion Reach, an original space strategy game.
Style/medium: polished hand-painted science-fiction game concept art, painterly realism, subtle brushwork, detailed believable materials, restrained cinematic lighting; not a photograph, not cartoon or anime.
Composition/framing: exactly ONE character, centered head and upper-chest bust, looking toward the viewer with a composed intelligent expression; shoulders slightly turned, face nearly frontal. Whole head visible with generous space above and beside it, eyes about 40 percent down the image. Strong readable silhouette and facial features at small UI size. Square 1024 by 1024 composition.
Scene/backdrop: understated deep charcoal-navy spacecraft embassy interior, softly out of focus, with a dark vignette and very faint architectural shapes. Background must not compete with the face.
Lighting/mood: soft cool key light from upper left, restrained warm rim light, dignified and thoughtful diplomatic encounter, readable face, no dramatic action.
Constraints: original character design, no text, no letters, no logo, no watermark, no frame or card layout, no weapons, no extra figures. This is a portrait asset, not a screenshot or poster.
Subject: a Terran human diplomat, a woman in her late forties with warm medium-brown skin, short swept-back salt-and-pepper hair, alert dark eyes, natural facial character and a calm confident expression. Practical elegant dark navy diplomatic uniform, subtle cyan seams and a small plain brass clasp, no insignia or lettering. Human anatomy and realistic proportions. Cyan and muted gold accents complement natural skin tones; no glowing eyes or alien traits.

### kharuun

Use case: stylized-concept.
Asset type: a standalone square character portrait for the diplomacy screen of Orion Reach, an original space strategy game.
Style/medium: polished hand-painted science-fiction game concept art, painterly realism, subtle brushwork, detailed believable materials, restrained cinematic lighting; not a photograph, not cartoon or anime.
Composition/framing: exactly ONE character, centered head and upper-chest bust, looking toward the viewer with a composed intelligent expression; shoulders slightly turned, face nearly frontal. Whole head visible with generous space above and beside it, eyes about 40 percent down the image. Strong readable silhouette and facial features at small UI size. Square 1024 by 1024 composition.
Scene/backdrop: understated deep charcoal-navy spacecraft embassy interior, softly out of focus, with a dark vignette and very faint architectural shapes. Background must not compete with the face.
Lighting/mood: soft cool key light from upper left, restrained warm rim light, dignified and thoughtful diplomatic encounter, readable face, no dramatic action.
Constraints: original character design, no text, no letters, no logo, no watermark, no frame or card layout, no weapons, no extra figures. This is a portrait asset, not a screenshot or poster.
Subject: a Kharuun envoy, an intelligent mineral-bodied alien species of crystalline builders. An original nonhuman face composed of interlocking warm dark basalt and translucent smoky-amber mineral plates, a broad angular cranium with small integrated crystal ridges rather than large spikes, deeply set luminous amber eyes and a subtle articulate mouth. Natural asymmetry and fine mineral strata suggest an ancient living organism, not a robot, human wearing rock armor, or generic hulking monster. Fine amber light glows gently in a few internal seams. Broad dignified upper torso in tailored charcoal metallic ceremonial clothing with understated bronze edging. Calm, thoughtful, trustworthy yet formidable expression. Clearly readable head and shoulders, no horns, no open roaring mouth.

### aelari

Use case: stylized-concept.
Asset type: a standalone square character portrait for the diplomacy screen of Orion Reach, an original space strategy game.
Style/medium: polished hand-painted science-fiction game concept art, painterly realism, subtle brushwork, detailed believable materials, restrained cinematic lighting; not a photograph, not cartoon or anime.
Composition/framing: exactly ONE character, centered head and upper-chest bust, looking toward the viewer with a composed intelligent expression; shoulders slightly turned, face nearly frontal. Whole head visible with generous space above and beside it, eyes about 40 percent down the image. Strong readable silhouette and facial features at small UI size. Square 1024 by 1024 composition.
Scene/backdrop: understated deep charcoal-navy spacecraft embassy interior, softly out of focus, with a dark vignette and very faint architectural shapes. Background must not compete with the face.
Lighting/mood: soft cool key light from upper left, restrained warm rim light, dignified and thoughtful diplomatic encounter, readable face, no dramatic action.
Constraints: original character design, no text, no letters, no logo, no watermark, no frame or card layout, no weapons, no extra figures. This is a portrait asset, not a screenshot or poster.
Subject: an Aelari scholar-diplomat, an original amphibious alien species of ocean-born archivists. Smooth pearlescent blue-teal skin, an elongated but broad nonhuman head, large dark glassy eyes with subtle violet iris rings, a small expressive mouth, delicate external gill fans close to the sides of the neck and head, and a low translucent cranial crest. Fine lavender bioluminescent markings trace the temples and cheek ridges. No human hair, no human nose, no elf ears; elegant amphibian anatomy rather than a human painted blue. Thoughtful and serene expression. Sophisticated dark indigo diplomatic mantle, hood down, subtle violet and silver detailing. The luminous features should remain subtle enough for a quiet dignified diplomatic portrait.
