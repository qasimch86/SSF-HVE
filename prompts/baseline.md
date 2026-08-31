You are writing a short explainer script from a research record.

Audience: {{AUDIENCE}}
Target spoken duration: about {{DURATION}} seconds.

Write the script from the research record below. Make it accurate and easy to follow.

Return ONLY a JSON object, with no prose before or after it, in exactly this shape:

{
  "case_id": "{{CASE_ID}}",
  "audience": "{{AUDIENCE}}",
  "target_duration_s": {{DURATION}},
  "beats": [
    {"beat": "short label", "narration": "what the narrator says",
     "on_screen": "what is shown", "claim_refs": []}
  ]
}

RESEARCH RECORD
---------------
{{SOURCE}}
