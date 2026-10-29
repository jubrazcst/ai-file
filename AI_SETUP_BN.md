# একই TOKEN দিয়ে OpenRouter AI — সেটআপ

এই সংস্করণ আগের আলাদা bot-token add-on-এর পরিবর্তে ব্যবহার করুন। আগের ai_addon চালাবেন না। এখানে bot token, Discord developer bot application বা নতুন dependency লাগবে না। নিজের বর্তমান TOKEN আগের Secrets-এই থাকবে।

## কী বদলেছে, কী একই
- TOKEN, GUILD_ID, CHANNEL_ID, SELF_MUTE, SELF_DEAF, status এবং python main.py entry point একই।
- keep_alive.py, requirements.txt, pyproject.toml, README.md, LICENSE original ZIP-এর সঙ্গে byte-for-byte একই।
- main.py-এ AI module import, responder তৈরি, incoming-message/heartbeat loop ও reconnect exception handling যোগ হয়েছে। Voice mute/deaf string actual JSON boolean-এ রূপান্তর করা হয়েছে।
- নতুন openrouter_ai.py-তে OpenRouter reply logic। API key না দিলে AI disabled থাকে। Model optional; ফাঁকা থাকলে OpenRouter account default ব্যবহার হয়।
- নতুন feature দিতে main.py-এর সংশ্লিষ্ট অংশ বদলানো আবশ্যক; পুরো source byte-for-byte অপরিবর্তিত দাবি করা হচ্ছে না।

## Setup: একই Secrets/Environment-এ যোগ করুন
আগের Secrets বদলাবেন না। OPENROUTER_API_KEY দিন; model দেওয়া বাধ্যতামূলক নয়:

| Name | Value |
| --- | --- |
| OPENROUTER_API_KEY | নিজের OpenRouter API key |
| OPENROUTER_MODEL | Optional: নির্বাচিত text model-এর exact ID; default চাইলে বাদ দিন |

OpenRouter key: https://openrouter.ai/settings/keys
Model list: https://openrouter.ai/models
Model ID নিজের নির্বাচিত model page থেকে কপি করুন; কোনো model স্থায়ী free/available ধরে নেওয়া হয়নি। Key-তে spending limit দিন। Token/key কারও কাছে পাঠাবেন না।

আগের মতো চালান:
```
pip install -r requirements.txt
python main.py
```
নতুন .env loader যোগ করা হয়নি: Secrets/environment variables ব্যবহার করুন, অথবা local shell-এ variables সেট করুন। নতুন bot token দেবেন না।

## ব্যবহার
- অন্য কেউ আপনাকে `@আপনার-account প্রশ্ন` লিখলে AI আপনার account থেকে reply পাঠাবে।
- আপনার message-এ Reply দিয়ে প্রশ্ন করলেও কাজ করবে, যদি Discord event-এ referenced_message-এর author তথ্য দেয়। সেই তথ্য না থাকলে false trigger এড়াতে reply trigger উপেক্ষা করা হয়; সরাসরি mention ব্যবহার করুন।
- নিজের message, bot/webhook message এবং unrelated text ignore করে।
- Default উত্তর শুরু হয় `AI: ` দিয়ে।
- Member লিখতে পারে `@আপনার-account !ai reset`—শুধু তার সেই channel-এর AI history clear।
- Help: `@আপনার-account !ai help`। এগুলো slash application command নয়, সাধারণ text।
- বাংলা/Banglish/English-এ প্রশ্নের ভাষা অনুযায়ী উত্তর দেওয়ার নির্দেশ আছে।

## Advanced options (একই Secrets-এ)
| Setting | Default | Range / meaning |
| --- | --- | --- |
| AI_ENABLED | true | false করলে AI off; মূল voice connection চলবে |
| AI_CHANNEL_IDS | empty | comma-separated text channel IDs; ফাঁকা হলে configured GUILD_ID-এর সব received text channel |
| AI_ALLOW_DM | false | true হলে received DM-তেও explicit mention/reply; স্বয়ংক্রিয় সব DM উত্তর নয় |
| AI_FOLLOWUP_SECONDS | 0 | 0–300; AI উত্তরের পরে একই member/channel-এর plain text follow-up সময়সীমা |
| AI_COOLDOWN_SECONDS | 8 | 1–3600; একই member/channel-এর request interval |
| AI_MEMORY_TURNS | 6 | 1–12; question-answer pair |
| AI_MEMORY_TTL_SECONDS | 1800 | 60–86400; idle expiry |
| AI_MAX_TOKENS | 200 | 32–2000; answer token limit |
| AI_TEMPERATURE | 0.7 | 0–2; model must support parameter |
| AI_HOURLY_REQUEST_LIMIT | 60 | 1–10000; logical jobs per process window |
| AI_REPLY_PREFIX | AI: followed by space | displayed reply prefix |
| AI_SYSTEM_PROMPT | built-in | custom language/tone/instructions |

Follow-up চাইলে AI_FOLLOWUP_SECONDS=60 দিন। Default-এ শুধু mention/reply-এ উত্তর। Cooldown বা queue পূর্ণ হলে অতিরিক্ত message ignore হয়। Queue সর্বোচ্চ ১০, একটিমাত্র AI worker; ৯০ সেকেন্ডের বেশি অপেক্ষা করা কাজ বাদ যায়। সর্বোচ্চ ৩০০ আলাদা conversation এবং ২০০০ recent message IDs রাখা হয়। Memory RAM-এ; restart-এ সব reset। Hourly cap টাকা-ভিত্তিক budget নয়; provider retry-তে সর্বোচ্চ দুই attempt হতে পারে। Help/reset admitted jobs-ও cap-এ গণনা হয়।

## Connection ও errors
AI API call background worker-এ হয়, যাতে heartbeat বন্ধ না হয়। Gateway sequence tracking, heartbeat ACK, reconnect event handling আছে। মূল reconnect wait ৩০ সেকেন্ড। এটি fresh session reconnect—resume/replay implement করা হয়নি; disconnect-এর সময়ের message মিস হতে পারে।
OpenRouter 429/502/503-এ সর্বোচ্চ একবার bounded retry; বড় Retry-After হলে retry করা হয় না। Discord send 429 হলে অপেক্ষা করে, একই message resend করে না। Discord 401/403 হলে AI pause হয়; restart করার আগে account/channel access পরীক্ষা করুন। Network timeout-এর পরে duplicate এড়াতে send retry হয় না। API failure console-এ সীমিত বার্তা দেয়; secrets/chat content log করে না।

## সীমা ও তথ্য
Text chat only: image analysis, speech, web search, moderation বা dashboard নেই। Existing voice-presence logic রাখা হয়েছে, পূর্ণ voice audio connection implement করা হয়নি; voice status বা 24/7 hosting সফল হবে—এমন নিশ্চয়তা নেই।
শুধু triggered text, per-member context ও explicit reply-এর quoted text OpenRouter/model provider-এ যায়। পুরো channel history fetch হয় না। Participants-কে AI reply ব্যবহারের কথা জানান।

Discord-এর official policy অনুযায়ী personal-user-token automation self-bot হিসেবে নিষিদ্ধ এবং account termination হতে পারে। এই কোডে CAPTCHA bypass, token harvesting, stealth বা permission bypass নেই; তা সত্ত্বেও policy restriction প্রযোজ্য। Public bot API documentation personal-token compatibility নিশ্চিত করে না। Live credentials দিয়ে পরীক্ষা করা হয়নি।
Policy: https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots

## Tests
```
python -m unittest test_openrouter_ai -v
```
১৯টি offline mocked test পাস: trigger/filters, duplicate/pending/hourly cap, queue bound, no-key disable, API payload/auth separation, retry handling, malformed output, Discord denial pause, no-ping replies, memory reset/isolation, emoji splitting এবং gateway READY/heartbeat/message dispatch। সব Python file syntax parse হয়েছে।

Real token/API দিয়ে login, gateway events, voice presence, permissions, provider model ও live reply পরীক্ষা হয়নি। নিজস্ব অনুমোদিত test channel-এ আগে যাচাই করুন।

## Render-এ এই সংশোধন লাগানো
এই আপডেটে শুধু runtime file openrouter_ai.py বদলেছে; আগের main.py বা TOKEN setup বদলাবেন না। ZIP থেকে openrouter_ai.py GitHub repository-র একই file-এর জায়গায় দিন এবং commit করুন।
Render → আপনার service → Environment-এ OPENROUTER_API_KEY নামটি ঠিক রাখুন, value-তে শুধু API key দিন। AI_ENABLED=false থাকলে true করুন। Default model চাইলে OPENROUTER_MODEL মুছে দিন বা ফাঁকা রাখুন। তারপর Save, rebuild, and deploy করুন যাতে নতুন code ও settings দুটোই চালু হয়।
Expected log: [AI] Enabled for mentions/replies; model=OpenRouter account default
এই log configuration enabled বোঝায়; key/credit/model live validation হয় প্রথম প্রশ্নে।
উত্তর ১–২ ছোট বাক্য দেওয়ার নির্দেশ, default ২০০ output tokens এবং সর্বোচ্চ ৫০০ characters।
Configured GUILD_ID-এর server-এ অন্য account থেকে @আপনার-account প্রশ্ন লিখে পরীক্ষা করুন। Reply ওই প্রশ্নের message-এই যাবে; অন্য member-কে আলাদা DM নয়।
Model বাদ দিলে account/payer default ব্যবহারের documentation: https://openrouter.ai/docs/api/reference/overview
