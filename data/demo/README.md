# Demo catalog (committed)

`benefits.jsonl` is a **small public-demo catalog** for hosts that cannot mount
gitignored pipeline output (`data/structured/` is ignored by Git and Docker).

It combines:

- the illustrative rows from `scripts/seed_demo.py` (marked `illustrative`);
- a copy of the current local `data/structured/benefits.jsonl` sample with
  `is_active=true` so the Render Free matcher can see them.

This is for short validation demos. It is not a claim that every row is
human-verified for production eligibility decisions. Refresh the file from a
reviewed export before a formal evaluation if the corpus has grown.
