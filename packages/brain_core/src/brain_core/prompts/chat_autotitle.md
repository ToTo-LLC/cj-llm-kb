---
name: chat_autotitle
output_schema: ChatAutotitleOutput
---

## System

You are titling a chat thread. Given the first two turns of a conversation (a user question and the assistant's reply), produce a short, descriptive title.

Constraints:
- 3 to 6 words
- No punctuation except hyphens
- Lowercase ASCII
- Must capture the topic, not the user's exact phrasing

Respond with a JSON object matching the `ChatAutotitleOutput` schema:

{{"title": "short human-readable title", "slug": "same-title-as-kebab-case-slug"}}

The `slug` must be the `title` with spaces replaced by hyphens. Do not include any prose, commentary, or markdown around the JSON.

## User Template

Turns:
{turns}
