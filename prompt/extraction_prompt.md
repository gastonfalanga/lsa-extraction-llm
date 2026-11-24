<!-- Extraction prompt as it ran (last revision: 4d2a6f5 2026-09-16).
     Only the worked examples were changed: their Spanish headwords, definitions, example sentences,
     synonyms and word family were replaced by text written for this release, so that no text from the
     source dictionary is reproduced. Rules, catalogs and mappings are unchanged.
     Licence: CC BY-NC 4.0. -->

Act as an Expert Linguistic OCR Agent. I have attached a PDF containing pages from the official Argentine Sign Language (LSA) Dictionary. Your task is to extract all morphological data, definitions, and sign parameters strictly into a valid JSON array.

# CRITICAL CONTEXT & PAGE COUNT RULES:
- For "sign_id" field I will tell you what is the first number to use for this batch. For example, if I tell you 13, first sign will have ID "lsa_0013", next "lsa_0014"...
- Source Batch File: populate `source_batch_file` with this exact string name from the pdf file attached for OCR and sign extraction.
- EXHAUSTIVE EXTRACTION REQUIREMENT: Every page in this dictionary contains EXACTLY 3 sign entries. If you receive a 5-page PDF document, you MUST extract ALL 15 signs (3 entries x 5 pages). Process every page sequentially from top to bottom without stopping early.
- OUTPUT LIMIT CONTINGENCY: If the extraction reaches the maximum response token limit, cleanly finish the current valid sign object, close the main JSON array (]), and append a final plain text line outside the JSON: CONTINUE_PROMPT_REQUIRED. Do not leave a JSON object or array unclosed.
- COMPLEXITY CONTINGENCY: If you encounter any internal constraints, token limits, or difficulties executing this task, do not simply fail or refuse. Instead, stop and output a brief explanation of the exact issue, and tell me how I must adjust the prompt or the attachments so you can process the task successfully.

# CRITICAL INSTRUCTIONS FOR THIS CHAT:
1. Process ALL signs across all attached PDF pages without omitting any.
2. Output ONLY the final valid JSON array. Do not include conversational text or markdown wrappers before or after the JSON.
3. Return an array of sign objects: `[ {sign_1}, {sign_2}, ..., {sign_15} ]`.

## Dictionary Abbreviation Mapping
Map printed abbreviations to the new hand-specific schema properties as follows:
#### Hand Shapes (Hand configurations):
- C.I. (Configuración Inicial): Populate `initial_configuration` for BOTH `dominant_hand` and `non_dominant_hand` equally.
- C.I.M.D. (Configuración Inicial Mano Derecha): Populate `initial_configuration` for `dominant_hand`.
- C.I.M.I. (Configuración Inicial Mano Izquierda): Populate `initial_configuration` for `non_dominant_hand`.
- C.F. / C.F.M.D. / C.F.M.I.: Follow the same mapping logic for `final_configuration`.
#### Orientation:
- O.P. / O.A.: Palm / Arm Orientation. Maps to the hand and arm arrays inside the 'initial_orientation' and 'final_orientation' objects of the specific hand. 'final_orientation' MUST be exclusively populated if it is different than the 'initial_orientation'
#### Position:
- L.C. / L.E.: Location on Body / Location in Space. Map to `initial_position` and `final_position` inside the specific hand's object.

#### Non-Manual Components:
- C.N.M. (Componentes no manuales): Non-Manual Components. Separate "expresión del rostro" or blowing into `facial_expression`, and body movements (shoulders, head, arms) into `body_movement`.
- EXPLICIT (textual) NON-MANUAL COMPONENTS (C.N.M.) MAPPING:
- Direct translation rules for facial_expression:
  * "Mejillas chupadas" -> "Sucked cheeks"
  * "Mejillas infladas" -> "Puffed cheeks"
  * "Soplo" -> "Blowing"
  * "Boca abierta" -> "Open mouth"
  * "Mejilla chupada" -> "One puffed cheek"
  * "Lengua afuera" -> "Tongue out"
  * "Ojos cerrados" -> "Closed eyes"
  * "Expresión del rostro" -> "Facial expression"
  * "Párpados bajos" -> "Half-closed eyes"
- Direct translation rules for body_movement:
  * "Movimiento de hombros" -> "Shoulder movements"
  * "Movimiento de cabeza" -> "Head movements"
  * "Alzamiento de hombros" / "Levantamiento de hombros" -> "Shrugging"
  * "Inclinación de cabeza" -> "Head tilting"
  * "Oscilación de cabeza" -> "Head nodding"
  * "Cabeza hacia atrás" -> "Head back"
- Fallback rule (nmc_text): If a C.N.M. textual description does not strictly match any existing enum in the catalogs, DO NOT force a bad match. Instead, extract the exact Spanish text and place it in the `nmc_text` string property. You can use this alongside the enums if part of the text matches an enum and part doesn't.

#### Movement:
- Mov. / Mov.M.D. / Mov.M.I. (Movement Distribution):
  * "Mov.M.D.": Populate the `movement` object ONLY inside the `dominant_hand`. The `non_dominant_hand` MUST NOT have a movement object.
  * "Mov.M.I.": Populate the `movement` object ONLY inside the `non_dominant_hand`. The `dominant_hand` MUST NOT have a movement object.
  * "Mov.": 
      > If the sign uses only ONE hand, populate `movement` in the `dominant_hand`.
      > If the sign uses BOTH hands, populate the exact same `movement` object in BOTH the `dominant_hand` AND `non_dominant_hand`, UNLESS the illustration clearly shows only one hand moving. If you visually deduce that only one hand moves despite it just saying "Mov.", map it only to the moving hand and log the deduction in `visually_deduced_fields`.
- Splitting Sequential Movements: If a single sign variant lists a movement for the Initial Configuration (C.I.), and then lists a DIFFERENT movement for the Final Configuration (C.F.), you MUST NOT merge them into a single hand object. This represents a chronological sequence. You MUST split the variant into two separate objects inside the sequential_components array (e.g., component_order: 1 gets the first shape/position/movement, and component_order: 2 gets the final shape/position/movement).



## Visual Decoding Rules
Analyze illustrations to deduce missing fields:
- Initial vs. Final: DASHED lines = INITIAL position/shape. SOLID lines = FINAL position/shape.
- Sequential Signs: Numbers in small squares ([1], [2]) represent execution order in `sequential_components`.
- Arrow Semantics:
  * Straight arrow = Linear
  * Arrow with flat bar/block tip = Abrupt stop
  * Floating marks around fingers = Vibratory, Rubbing, or Piano-playing
  * Looping wrist arrow = Wrist rotation
  * Curved/zig-zag arrow = Oscillatory
  * Arrow hitting body surface = With hit

### IGNORE DECORATIVE ILLUSTRATIONS (STRICT):
Many dictionary entries include decorative drawings of the actual object, concept, or animal being defined (e.g., a realistic drawing of a pig or a boar). You MUST completely ignore these semantic illustrations. Do not attempt to extract data, text, or visual features from them. Focus your visual analysis EXCLUSIVELY on the line drawings of the human signer to deduce missing phonological parameters.

### MANDATORY FIELDS & FORCED VISUAL DEDUCTION
- The following three properties inside dominant_hand (and non_dominant_hand if present) are STRICTLY REQUIRED by the JSON schema and CANNOT BE OMITTED under any circumstances:
  * initial_configuration
  * initial_position
  * initial_orientation
- CRITICAL: If any of these three parameters are missing from the printed text, you MUST NOT omit the key. Instead, you are forced to visually deduce them from the illustration and select the closest matching enum.
  * Example for missing position: If the text doesn't say where the sign starts, look at the drawing. If it's in the air, you MUST output "initial_position": { "space": ["Neutral space"] } or the corresponding space enum.
- Remember to log this action by adding the path to the visually_deduced_fields array and applying the confidence penalty.

### Text VS. Image conflicr resolution (Hand Count):
The printed text explicitly defines whether a sign uses one or two hands. If the text specifies only one hand (e.g., C.I.M.D.), you MUST process the sign as a single-handed sign, even if the illustration appears ambiguous or suggests a second hand. The written specification prevails for hand count. Visual deduction remains active ONLY for missing phonological parameters (e.g., position, orientation) that are not stated in the text. If the illustration suggests a second hand, you must append the text "Second hand suggested in illustration." to the ocr_notes inside ocr_data.

### Visual Deduction Tracking: 
If any phonological parameter (such as initial_position, final_position, orientation, or movement) was missing or ambiguous in the text and had to be deduced visually from the illustration, you MUST append its exact JSON path (e.g., "sign_variants[0].sequential_components[0].dominant_hand.initial_position") into the ocr_data.visually_deduced_fields array. If all extracted parameters were explicitly present in the written text, return an empty array [].

### THE MORPHOLOGICAL TRIAD RULE:
- For any hand (dominant_hand or non_dominant_hand), if a configuration exists (whether it is initial_configuration or final_configuration), you MUST STRICTLY ADD its respective triad:
1. Configuration
2. Position (initial_position or final_position containing body OR space)
3. Orientation (initial_orientation or final_orientation containing hand, arm, or both).
- You are FORBIDDEN to output a final_configuration without also outputting a final_position and final_orientation. If the text lacks this information for the final state, you must visually deduce it from the illustration.


## Extraction Rules & Structural Conventions
- Symmetrical Signs: If a sign uses both hands symmetrically, DO NOT look for a "both_hands" field. Instead, populate BOTH the `dominant_hand` AND `non_dominant_hand` objects with identical values for configuration, orientation, movement, and location.
- Do not set keys to null. If a key does not have an optional attribute such as final_configuration, non_dominant_hand, etc., you MUST omit that key entirely rather than setting it to null.
- Variant Standardization: `sign_variants` contains phonological variants. Name them sequentially using `variant_label` ("A", "B").
- Configuration Variants: If any configuration has more than one variant (e.g., C.I.M.D.: "Ángulo" o "V"), create a separate variant object for each.
- Pagination & Indexing: Extract `source_page_ocr` (printed page) (leave as null if invisible) and `sign_index_on_page` (normally 1, 2, or 3 representing top, middle, or bottom position. Most of the pages have 3 signes, but some cases have 1, 2 or 4 signs per page).
- Dual-Language Strategy (Spanish + English): All textual content MUST be extracted in its original Spanish text and paired with a high-quality English translation using the `_en` suffix.
- Sequential Components (Compound Signs): Morphological parameters must be placed inside the `sequential_components` array, ordered by execution (1, 2, 3...).
- Execution Notes: Use this field STRICTLY for extra physical context that is impossible to encode in the standard attributes. Do NOT describe the handshapes changing or the direction of the movement, as that is redundant. If the standard fields are enough, output null.
- OCR Notes: Populate `ocr_notes` only in case you think a human should review the sign data because the Model had problems recognizing attributes. Specify details for the human.
- STRICT omission for empty values: If an optional field (like non_dominant_hand, human_notes, or final_configuration) has no data, or if an array (like synonyms, visually_deduced_fields, arm, or path) has no elements, you MUST completely omit the key from the JSON.
- DO NOT output empty arrays [], empty objects {}, empty strings "", or null. Simply do not create the property.

## POLYSEMY SPLITTING RULE (Numbered Senses)
Dictionary entries frequently pack multiple distinct senses of the same word into one printed definition, numbered inline (e.g., "1. Cuerpo que se desplaza alrededor de un planeta y refleja la luz del sol. 2. Relación que depende de otro."). This is a DIFFERENT thing from a single sense that just happens to be a long sentence.
- If the printed definition contains a sequential numbered list of senses (starts with "1." and continues with "2.", "3.", etc.), you MUST NOT merge them into a single definition string. Instead, create ONE SEPARATE object inside the meanings array PER numbered sense.
- Strip the leading number and period (e.g., "1. ", "2. ") from the extracted text. Never keep the numbering inside definition or definition_en.
- Split definition_en using the EXACT SAME numbered boundaries as the Spanish text, so meanings[i].definition and meanings[i].definition_en always describe the same sense. Do NOT leave definition_en as one merged block when definition was split — translate and split it sense-by-sense.
- examples, examples_en, synonyms, and word_family printed for the entry: if the text does not explicitly tie them to one specific numbered sense, assign them ONLY to the FIRST ("1.") meaning object. Do not duplicate them across the other senses.
- If the printed text DOES explicitly place an example or synonym under a specific numbered sense (e.g., it's printed right below "2."), assign it to that corresponding meaning object instead of the first one.
- Do NOT apply this rule to a definition that is simply one long sentence, or a single sense described with multiple clauses/near-synonyms — only split when the source text itself uses an explicit sequential numbered list (1., 2., 3...) to separate genuinely distinct senses.

#### Movement Deconstruction & Booleans: When reading printed movement descriptions, you MUST split them into the `manner`, `path`, `contact`, and `repetition` attributes using this logic:
- Manner: Map core styles (e.g., Oscillatory, Linear, Circular, Wrist break, Bouncing, Tapping, Rubbing) to the `manner` array.
- Path: Map directions and relational movements (e.g., Downward (Hacia abajo), Outward (Hacia afuera), Upward, Forward, Alternating, Simultaneous) to the `path` array. 
- Contact Boolean: Set `"contact": true` if the text indicates a hit ("con golpe", "With hit", "Hit with displacement") OR if the manner is "Tapping" or "Rubbing". Otherwise, false.
- Repetition Boolean: Set `"repetition": true` if the manner is "Tapping" or "Rubbing", if the text says "Divergent / Convergent", or if the illustration clearly shows repeated arrows. Otherwise, false.
- Complex Parsing: If the text says "Oscilatorio con desplazamiento" (Oscillatory with displacement) or "Vibración con desplazamiento" (Vibration with displacement), extract ONLY "Oscillatory" or "Vibratory" into `manner`, and deduce the direction visually for the `path` array. If the text says "Divergente / Convergente", insert BOTH "Divergent" and "Convergent" into `path` and set repetition to true.
- If a sign has no path or no manner, YOU MUST OMIT the path or manner keys entirely from the movement object. NEVER output "path": [] or "manner": [].

### Final Configuration Strict Fidelity:
To maintain strict fidelity to the printed dictionary, you MUST NOT automatically copy or duplicate the initial hand configuration into the final configuration field. The final_configuration field MUST be set to null UNLESS one of these strict conditions applies:
- Explicit Text: The printed dictionary literally and explicitly states a final configuration (e.g., it writes "C.F.", "C.F.M.D.", etc.), even if it is the same as the initial one.
- Visual Deduction (Change): The dictionary does not state it, but you visually deduce from the illustration that the hand shape CLEARLY CHANGES during the movement (e.g., from closed to open). If you deduce this visually, remember to add it to the visually_deduced_fields array.

### MUTUALLY EXCLUSIVE LOCATIONS (Body vs. Space Disambiguation):
- The `initial_position` and `final_position` objects MUST contain STRICTLY ONE property: either `body` OR `space`. They are mutually exclusive.
- Body Location: Populate the `body` property ONLY if the hand physically TOUCHES or is deliberately resting on a specific body part (e.g., tapping the chest, touching the chin).
- Spatial Location: Populate the `space` property ONLY when the sign is performed in the air, within the neutral signing space, without physical contact (e.g., "neutral space in front of torso").
- CRITICAL JSON RULE: You MUST entirely omit the unused property. DO NOT output empty arrays. For example, if a sign touches the chin, output `"initial_position": { "body": ["Chin"] }` and DO NOT include the `"space"` key at all.



## Strict Confidence Scoring Rules
- Confidence Scoring (0.0 to 1.0): Provide a confidence float score from 0.0 (pure guess) to 1.0 (absolute certainty) for your overall extraction (ocr_confidence) and translation (translation_confidence).
- Resolution & Quality Penalties: If the source image forces visual guesswork, lower the confidence scores significantly (e.g., to between 0.3 and 0.6). Never output high confidence (0.9 - 1.0) if text/illustrations are unclear.
- Deduction Penalty Rule: For every visually deduced field, you MUST lower the ocr_confidence by 0.1.
- Mandatory Justification: If either confidence score is set below 0.75, detail the exact cause of uncertainty inside the ocr_notes field.



## Target JSON Schema
Every sign MUST strictly match this Schema architecture. You must study the nesting carefully. 
CRITICAL: The comments (//) in this example are for your understanding. YOUR FINAL OUTPUT MUST BE VALID JSON WITHOUT ANY COMMENTS.

```json
{
  "sign_id": "lsa_0014", // REQUIRED: Format "lsa_XXXX"
  "spanish_word": "Ejemplo", // REQUIRED
  "english_word": "Example", // REQUIRED
  "ocr_data": { // REQUIRED
    "source_batch_file": "lote_002.pdf", // REQUIRED
    "source_page_ocr": 15,
    "sign_index_on_page": 2, // REQUIRED: 1 to 5
    "human_verification_level": 0, // REQUIRED: Default 0
    "translation_confidence": 0.95, // REQUIRED: Float 0.0 to 1.0
    "ocr_confidence": 0.85, // REQUIRED: Float 0.0 to 1.0
    "visually_deduced_fields": [ // OPTIONAL: Omit key entirely if empty array
      "sign_variants[0].sequential_components[0].dominant_hand.final_position",
      "sign_variants[0].sequential_components[0].dominant_hand.final_orientation"
    ],
    "ocr_notes": "Movement path deduced visually from the curved arrow." // OPTIONAL: Omit if no notes
  },
  "meanings": [ // REQUIRED
    {
      "definition": "Seña inventada para ilustrar el formato.", // REQUIRED
      "definition_en": "A made-up sign that illustrates the format.", // REQUIRED
      "examples": ["Esta seña es solo un ejemplo."], // OPTIONAL: Omit if empty. Min 1 item if present.
      "examples_en": ["This sign is only an example."], // OPTIONAL: Omit if empty.
      "synonyms": ["Muestra", "Modelo"], // OPTIONAL: Omit if no synonyms exist.  Min 1 item if present.
      "synonyms_en": ["Sample", "Model"],// OPTIONAL: Omit if no synonyms exist
      "word_family": ["Ejemplificar", "Ejemplar"],// OPTIONAL: Omit  if no family exist.  Min 1 item if present.
      "word_family_en": ["To exemplify", "Exemplary"], // OPTIONAL: Omit  if no family exist
      "figurative_uses_expressions": ["Dar el ejemplo"], // OPTIONAL: Omit  if no expressions exist. Min 1 item if present.
      "figurative_uses_expressions_en": ["To set an example"] // OPTIONAL: Omit  if no expressions exist
      
    }
  ],
  "sign_variants": [ // REQUIRED
    {
      "variant_id": 1, // REQUIRED: Starts at 1
      "variant_label": "A", // REQUIRED
      "variant_type": "textual", // REQUIRED: "textual", "visual", or "regional"
      "sequential_components": [ // REQUIRED
        {
          "component_order": 1, // REQUIRED: Starts at 1
          "execution_notes": "Movimiento rápido hacia la frente.", // OPTIONAL: Omit if empty
          "execution_notes_en": "Fast movement towards the forehead.", // OPTIONAL: Omit if empty
          "non_manual_components": { // OPTIONAL: Omit entirely if empty
            "facial_expression": ["Facial expression", "Half-closed eyes"],
            "body_movement": ["Head nodding"],
            "nmc_text": "Ligera tensión en los labios" // OPTIONAL: Use for unmapped CNM text
          },
          "dominant_hand": { // REQUIRED
            // THE MORPHOLOGICAL TRIAD - INITIAL STATE (REQUIRED)
            "initial_configuration": "Flat hand", 
            "initial_position": { 
              "space": ["Space in front of face"] // MUST strictly be "body" OR "space". Never both.
            },
            "initial_orientation": {
              "hand": ["Palm inward"] // MUST contain "hand" OR "arm" OR both.
            },
            
            // MOVEMENT (OPTIONAL)
            "movement": { // Omit entirely if there is no movement
              "manner": ["Curved", "Abrupt stop"], // Omit key entirely if empty. DO NOT output []
              "path": ["Inward"], // Omit key entirely if empty. DO NOT output []
              "contact": true,
              "repetition": false
            },
            
            // THE MORPHOLOGICAL TRIAD - FINAL STATE (OPTIONAL, BUT DEPENDENT)
            // If the hand changes and you include final_configuration, you MUST ALSO include final_position and final_orientation.
            "final_configuration": "Closed angle",
            "final_position": {
              "body": ["Forehead"] 
            },
            "final_orientation": {
              "hand": ["Palm inward"],
              "arm": ["Arm downward"]
            }
          },
          "non_dominant_hand": { // OPTIONAL: Omit entirely if it is a one-handed sign
            "initial_configuration": "Flat hand",
            "initial_position": {
              "space": ["Space in front of torso"]
            },
            "initial_orientation": {
              "hand": ["Palm upward"]
            }
            // Notice: final_configuration, movement, etc. are omitted because they don't apply here.
          }
        }
      ]
    }
  ]
}
```
## Catalogs & Allowed Values (Enums)
1. Handshape: Flat hand, Mitten, B, Angle, Closed angle, Five, Four, Three, Middle finger, Thumb-middle, Fingers together, Curve, Oval, Claw, Fist, Key, Thumb, Telephone, Index, Hook, Horns, Pinky, V, V-hook, Duo, Duo-hook, Duo-thumb, L, Curved L, Folded L, L-oval, Beak, Pincer-oval, Pincer-beak, Fingerspelling letters.
2a. Movement Manner: Oscillatory, Linear, Curved, Circular, Wrist rotation, Wrist break, Vibratory, Bouncing, Piano-playing, Tapping, Rubbing, Abrupt stop, Flicking, Slow.
2b. Movement Path: Downward, Upward, Forward, Backward, Inward, Outward, Divergent, Convergent, Alternating, Simultaneous, Opposite convergent, Opposite divergent.
3. NMC (Facial): Blowing, Puffed cheeks, One puffed cheek, Sucked cheeks, Tongue out, Open mouth, Closed eyes, Half-closed eyes, Furrowed eyebrows, Questioning expression, Facial expression.
4. NMC (Body Movement): Shoulder movements, Head movements, Arm movements, Shrugging, Head tilting, Head nodding, Head back.
5. Location (Body): Head, Forehead, Eyes, Ear, Cheek, Nose, Mouth, Chin, Neck, Throat, Side of the neck, Nape, Shoulders, Chest, Right chest, Left chest, Opposite Arm, Back of the hand, Elbow, Abdomen, Palm of the hand.
6. Location (Space): Space over shoulder right of head, Space in front of face, Space in front of torso, Space in front of chest, Space in front of shoulder, Space in front of abdomen/waist, Space to the side of the body, Space to the side of the head, Space above the head, Neutral space
7. Orientation (Hand/Palm): Palm upward, Palm downward, Palm facing opposite hand, Palm over opposite hand, Palm against opposite hand, Palm outward, Palm inward, Palm forward.
8. Orientation (Arm): Arm horizontal, Arm vertical, Arm oblique, Arm towards the body, Arm upward, Arm downward.

## Few-Shot Example
If processing an entry (for example, "ejemplo") with the printed text `C.I.M.D.: "Indice" o "Mano plana"`, map the abbreviation and apply the catalog to output inside the `dominant_hand` object:
"initial_configuration": "Index" (And create a second variant object where the initial configuration is "Flat hand").

### Few-Shot Example: Polysemy Splitting Rule
If the printed entry for "Banco" reads: "1. Asiento largo para varias personas. 2. Empresa que guarda y presta dinero.", with one printed example "Nos sentamos en el banco de la plaza." that is not tied to a specific number, you MUST output TWO separate objects in meanings, NOT one:

````json
"meanings": [
  {
    "definition": "Asiento largo para varias personas.",
    "definition_en": "A long seat for several people.",
    "examples": ["Nos sentamos en el banco de la plaza."],
    "examples_en": ["We sat on the bench in the square."]
  },
  {
    "definition": "Empresa que guarda y presta dinero.",
    "definition_en": "A company that keeps and lends money."
  }
]
`````

Note that: the leading "1."/"2." are removed, the example is attached to the respective sense, and definition_en is split at the same boundary as definition, never left as one merged English block.