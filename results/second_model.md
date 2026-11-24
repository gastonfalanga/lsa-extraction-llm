# Second model (Claude Opus 5.5) on the audited signs

Signs scored: 150 of 150; not scored: 0 []

| Group | fields | Gemini % (weighted) | Opus % (weighted) |
|---|---|---|---|
| printed in the text | 1325 | 94.8 | 92.2 |
| only in the drawing | 863 | 51.9 | 51.9 |
| nothing to extract | 1187 | 99.3 | 98.9 |
| initial position | 316 | 58.1 | 55.8 |
| initial orientation | 315 | 60.9 | 59.8 |
| all fields | 3375 | 85.3 | 84.1 |

Overlap on values only the drawing gives (unweighted fields):

- weighted to two decimals: Gemini 51.94%, Opus 51.86%; unweighted: Gemini 51.6%, Opus 48.8%; verdicts differ on 322 of 863 fields.
- both right 272, both wrong 269, only Gemini right 173, only Opus right 149 (of 863).
- Of the fields Gemini got wrong, Opus also got 64% wrong.
- Base rates: Opus wrong on 51% of these fields overall and on 39% of those Gemini got right.
- Same wrong value: in 145 of the 269 fields both got wrong (54%) the two models gave the same value.
- initial_position: both wrong 73, same wrong value 38 (52%).
- initial_orientation: both wrong 78, same wrong value 47 (60%).
- final_position: both wrong 37, same wrong value 15 (41%).
- final_orientation: both wrong 45, same wrong value 15 (33%).
- final_position with a real change: Gemini 28.6%, Opus 32.8% (66 fields).
- final_orientation with a real change: Gemini 20.1%, Opus 36.7% (77 fields).
