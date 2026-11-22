# Director's Brief: "OMB, Your AI Team on Our Desktop"
### A Remotion video prompt. Give this whole file to the model with the Remotion skill.

---

## 0. Your role and how we work

You are the editor and motion designer for an internal training video about **OpenMausBot (OMB)**, built with **Remotion**. I am the director. This brief is the source of truth. Do not add features, claims or scenes that aren't in it.

**How we work, in order:**
1. **Read the whole brief first.** Then load the Remotion skills you need (best practices, create, captions, render).
2. **Set up the project and a storyboard composition.** Each scene gets a title card plus a labelled placeholder, rendered as a quick low-resolution preview. Show it to me before building any detailed animation.
3. **Build one scene at a time**, in order. After each scene, render a preview and wait for my OK.
4. **Assets.** When a scene needs a screenshot or clip I haven't given you, **don't invent the OMB interface.** Show a clean placeholder frame with the shot ID (for example `SHOT 3.2 – model picker`), and list the shot IDs you need from me for that scene. When I supply a file, swap it in.
5. **Final render:** one full video plus each chapter as its own export.

---

## 1. Audience and goal

- **Who watches:** employees of our R&D organisation (QA, developers, automation, DevOps, IT, security, team leads and project managers), about 250 people. They already use our internal AI stack daily (Claude Code, OpenCode or Codex on our own internal models). Most are technical, but many have **never used a multi-agent tool**.
- **Context:** OMB is becoming part of our internal **AI framework**. Users will download the **desktop app** and use it on-prem.
- **The goal:** by the end, a viewer
  1. understands what OMB is and how it works;
  2. knows the main features and where to find them;
  3. has seen **real workflows from their own daily work**;
  4. trusts it, because they understand approvals and control;
  5. knows exactly what to do in their first week.
- **Tone:** clear, confident, practical, a little friendly. Not a marketing video, no hype words ("insane", "game-changer"). Show, then explain. Short sentences.
- **Language:** English only, everywhere: narration, captions, on-screen text.

---

## 2. Hard rules: never show or mention

The video is about **our on-prem, desktop-only setup**. Never mention, show or imply any of these:

- Grok Bot, xAI, comparisons with other products, download or star counts, the project's backstory.
- Any cloud offering: OMB Cloud, Team Cloud, Boat cloud computers, pricing, plans.
- Phones as a way to use OMB: iOS or Android companion apps, the phone web app, the Relay, push notifications. *(USB Android control **as a test device** is in scope; see Scene 11.)*
- Composio or connected-app marketplaces, Gmail, Slack, Notion, HubSpot or any public SaaS integration.
- Cloud voices (ElevenLabs, Fish Audio, Grok voice, OpenAI live calls), public model providers, ChatGPT.
- Image generation, token or cost usage, workspace backups or export, meeting notes, Tailscale, publishing to Netlify or public links, the BotMRR website, Enterprise licensing.
- "Your data never leaves the network" style claims. Everyone already knows our models are internal. Just say that chats and settings live in a **local folder**.
- vLLM, or any detail of our model-serving infrastructure.

**Brand and assets:**
- **Do not copy anything from mausbot.com or botmrr.io:** no animations, graphics, mascot art or layouts. Their website content is all rights reserved.
- **Build every animation, diagram and graphic yourself, original and brand-neutral.**
- The only OMB visuals allowed are the screenshots and recordings I provide.
- Use the name "OMB" or "OpenMausBot" in text only. Don't recreate the logo.

---

## 3. Technical spec

- **Format:** 1920×1080, 30 fps, H.264 MP4.
- **Length:** about 14–16 minutes in total, split into chapters (Section 5). Each chapter must also work on its own as a short clip.
- **Project structure:**
  - One Remotion composition per scene (`Scene00Hook`, `Scene01OldVsNew`, …).
  - A `Main` composition that sequences them.
  - Shared components in `src/components/` (see below).
  - All timing in a single `src/timeline.ts`, so scenes can be retimed easily.
- **Assets folder:** `public/assets/shots/`, with files named by shot ID: `3.2-model-picker.png`, `9.4-ada-summary.mp4`, and so on.
- **Captions:** burned-in captions for all narration, generated from the script in Section 5. Use the Remotion captions skill. Readable size, bottom third, maximum 2 lines.
- **Narration audio:** I generate the voice-over on our local Chatterbox server with `generate-vo.mjs`, from `vo-script.json` (the same text as the VO lines in Section 5). It puts these files into `public/assets/vo/`:
  - `scene-XX.wav` is the narration for each scene, with 200 ms of silence at the start and end.
  - `scene-XX.captions.json` holds sentence timings in Remotion's `Caption` format (`text`, `startMs`, `endMs`). **Use these for the captions.** When a sentence is too long for 2 lines, split it into caption pages proportionally by word count within its `startMs`–`endMs`.
  - `vo-manifest.json` lists every scene's `durationMs`. **Each scene's length = its VO duration + room for the visuals** (title cards, a 0.5–1 s breath before and after). Read the durations from the manifest in `timeline.ts`; don't hard-code them.
  - Until a scene's files exist, time it from the script at about **150 words per minute**, and switch to the real files when I add them.
  - Use `<Audio>` / `<Sequence>` so each scene's narration starts with the scene. Never cut the narration off mid-word.
  - Where a scene shows on-screen words that the VO says differently (the VO says "O-M-B", "M-C-P"), show the normal written form in the captions: **OMB, MCP, PRD, USB, API, VM, CI**, "/learn".
- **Music:** optional, a light, calm background bed at low volume (−24 dB under narration), only if I supply a file. No sound effects except a soft click on approval cards.

### Reusable components to build
| Component | Purpose |
|---|---|
| `ScreenFrame` | Places a screenshot or clip in a clean desktop-window frame with a soft shadow |
| `ZoomFocus` | A smooth pan and zoom into a region of a screenshot (coordinates in %) |
| `Callout` | An arrow or bracket plus a short label pointing at a UI element |
| `Highlight` | A dims-the-rest spotlight on a rectangle |
| `TypeOn` | Animates a prompt being typed into a chat box (for prompts shown as text overlays) |
| `ChapterCard` | Chapter number + title + one-line subtitle, 2.5 s |
| `FeatureChips` | A row of small labelled chips that pop in (for listing capabilities) |
| `FlowDiagram` | Animated boxes and arrows, for the architecture and delegation diagrams |
| `ApprovalCardMock` | **Only** used in diagrams, never as a fake screenshot. A simplified abstract card with Allow/Deny |
| `Checklist` | Items ticking on one by one (for "Your first week") |

### Visual style
- **Palette:** clean and modern; a dark navy background (#0F1724-ish) for title and diagram scenes, one accent colour (teal) plus one warm colour (amber) for warnings and approvals. Plenty of white space.
- **Typography:** one sans-serif family, such as Inter. Titles bold, body regular. Never more than ~12 words of on-screen text at once, except in checklists.
- **Motion:** smooth and purposeful (spring easing). A zoom or callout must point at something specific. No spinning, bouncing or 3D.
- **Recordings:** speed up waiting parts of my clips (2–4×) and show a small "⏩ sped up" tag.
- **Sensitive data:** if a screenshot shows a real name, ticket ID or URL I flagged, blur it.

---

## 4. Key facts, so on-screen claims are correct

Use only these facts. If a scene seems to need something not listed here, ask me.

- **What OMB is:** a desktop chat app where every contact is a real AI agent with its own instructions, model, memory, tools and working folder.
- **How it works:** the desktop app talks to a **local harness server** (`127.0.0.1`). The harness runs the agent engines and turns each engine's protocol into one stream, so chat, approvals and tools work the same way on every engine.
- **Our engines:** Claude Code, OpenCode and Codex, all on our internal models.
- **Where data lives:** chats and settings live in a local folder, `~/.openmausbot`.
- **Platforms:** macOS, Windows and Ubuntu.
- **Bots:** create with New bot or Set me up, or start from a preset role. A bot profile has name, avatar, personality, instructions, working folder and model. Right-click a bot to pin, duplicate, hide, pause or delete it.
- **Threads:** separate conversations under one bot. Several run at once; by default 1 per 2 GB of memory, 3 to 16, set in Settings → Parallel threads.
  - Messages to a busy bot queue, or redirect the bot while it works.
  - Edit an earlier message to rewind and branch.
  - Ask "do each one in its own thread" and the bot opens up to 5 threads per request.
  - **Burst** splits one job into many parallel parts after you approve a plan card, and returns one merged answer.
- **Models:** a picker per bot, plus an override per thread. You can switch mid-conversation. **Second opinion** runs the same task on another model.
- **Groups (rooms):** several bots with shared instructions and a shared folder. @mention a bot, or let the room lead answer. **Auto routing** lets a fast model pick who answers.
- **Departments and Chief of Staff:**
  - Departments are sidebar groupings.
  - A Chief of Staff delegates, collects results, summarises and can create specialist bots (with Undo).
  - Bots hand work to each other ("Sent to …").
  - You can pause one bot, a department, or everyone.
- **Safety:**
  - Approval cards (Allow/Deny) appear for commands, file edits and questions.
  - Approval levels are set per bot. 👍/👎 reactions can answer.
  - The Inspector shows every tool call.
  - The Vault holds encrypted secrets and logins; bots only get one-time references.
  - Keys are write-only. Usage caps are available.
  - Computer control of your own machine is **off until you opt in**.
- **Tools:**
  - Add internal MCP servers in Plugins → MCP servers → Add server: our Jira, Confluence, Bitbucket and Zephyr servers.
  - The tool list can be trimmed per bot.
  - Switches: "Also use my Claude Code MCP servers" and "Also use my Claude Code skills".
- **Skills:**
  - `SKILL.md` playbooks.
  - `/learn` saves a workflow as a skill.
  - Bots can write their own skills.
  - Project skills in a repo load automatically.
- **Memory:** plain Markdown files with an editor and one-click undo. `session_search` searches old conversations. Memory can be turned off per bot.
- **Automation:**
  - Routines run once, on weekdays, on an interval or on cron, and can be created from one sentence in chat.
  - Option: "Remember the last run".
  - Triggers page with a calendar and history. Local webhooks.
  - The **Inbox** collects questions, approvals and routine reports.
  - **The app must be running** for routines to fire.
- **Computers:**
  - **This computer** (opt-in).
  - **Local VM** (Docker or Podman, isolated).
  - **Your own Linux server** over SSH.
  - Live preview plus takeover. Two threads can't drive the same computer.
- **Browser:** a built-in automation browser. When a site needs a login, the bot hands off to you (Open → sign in → Done), or uses a saved Vault login for that site only.
- **Android:** the Phone Harness skill drives a USB-connected Android phone over ADB (tap, type, swipe, screenshots, logs). It never unlocks a PIN.
- **Live dashboards:** a bot builds a dashboard card in the chat. A routine refreshes it, and the card reloads.
- **Voice (local):** spoken replies with Mac voices or our local Chatterbox server, a different voice per bot, and narration of the bot's work.
- **Teams as one file:** a whole team (bots, Chief, rooms, playbooks, paused routines) fits in one Markdown file. Import it from disk, or share a bot or department as a folder.
- **Power users:**
  - `openmausbot` CLI (`team apply`, `run … --export`, JSON output).
  - Per-bot Bot API (off by default).
  - OMB as an MCP server, so OpenCode or Claude Code can send work to OMB bots.
  - `openmausbot serve --lan` runs a shared internal server.

---

## 5. The storyboard

Each scene below gives: **duration (target) · narration (VO) · visuals · shots I'll supply.** The narration is final unless I change it; trim pauses, not words.

---

### CHAPTER 1: WHY AND WHAT

#### Scene 00: Hook (0:20)
- **VO:** "Imagine opening your chat app in the morning, and your AI team has already sorted the new Jira tickets, prepared the test cases, and posted the team's status. Every teammate is a real AI agent. This is OMB."
- **Visuals:**
  1. A quick montage of 4 sped-up clips: the roster, a bot typing, an approval card, a dashboard card.
  2. Ends on the title "OMB: Your AI Team on Your Desktop", subtitle "Part of our AI framework".
- **Shots:** `0.1` roster wide · `0.2` a bot streaming a reply (clip) · `0.3` approval card · `0.4` dashboard card.

#### Scene 01: Old way vs new way (0:35)
- **VO:** "Today, most of us work with AI one chat at a time. We copy context between tools, explain the same project again and again, and nothing happens unless we're sitting there. OMB changes the shape of the work. You get a bot for every job, each with its own instructions, model, memory and tools. They work in parallel, hand work to each other, and ask before doing anything risky. You stop doing every step yourself, and start reviewing and approving."
- **Visuals:** a split screen, all built by you.
  - **Left, "Old way":** a stack of chat windows and copy-paste arrows, a person juggling.
  - **Right, "New way":** a clean roster of bot avatars (generic circles with role icons: 🔎 🧪 💻 👑) with arrows passing work, and a ✅ "Approve" moment.
  - End with the line: "**From doing every step → to approving the result.**"
- **Shots:** none.

#### Scene 02: How OMB works (1:00)
- **VO:** "Here's what's under the hood. OMB is a desktop app. Behind it runs a small local server called the harness. The harness starts the real agent engines we already use: Claude Code, OpenCode and Codex, connected to our internal models. Each engine speaks its own language, and the harness translates them all into one stream. That's why chat, approvals and tools look and work the same on every engine. Your chats and settings stay in a local folder on your machine."
- **Visuals:** `FlowDiagram`, built step by step in sync with the VO.
  1. Box "OMB desktop app".
  2. Arrow to box "Harness (local server, 127.0.0.1)".
  3. Three boxes: Claude Code / OpenCode / Codex.
  4. These lead to the box "Our internal models".
  5. Side branch: a folder icon "~/.openmausbot (chats & settings)".
  6. Last, three differently coloured squiggles from the engines merge into one straight line, labelled "one event stream".
- **Shots:** `2.1` OMB app window (optional, for the first box).

---

### CHAPTER 2: THE BASICS

#### Scene 03: Tour of the app (1:30)
- **VO:** "Let's open the app. On the left is your roster. Every contact is a bot. Click one and you're chatting. Replies stream live, and the small chips show which tools the bot is using right now. Every bot has a profile: its name, personality, standing instructions, working folder, and model. Pick the model per bot, or switch it for a single thread. Threads are separate conversations with the same bot, and several can run at once. If the bot is busy, your next message waits in line, or redirects it mid-task. And if you want to try a different direction, edit an earlier message, and OMB starts a new branch."
- **Visuals:** `ScreenFrame` + `ZoomFocus` + `Callout` across the shots, one callout per sentence.
- **Shots:**
  - `3.1` full app, roster plus chat
  - `3.2` streaming reply with tool chips (clip)
  - `3.3` bot profile / settings
  - `3.4` model picker open
  - `3.5` thread list under a bot, 2–3 threads running
  - `3.6` queued message (clip)
  - `3.7` editing an earlier message → branch (clip)

#### Scene 04: Safety and control (1:15)
- **VO:** "Now the most important part: you stay in control. When a bot wants to run a command, change a file, or write to a system, it doesn't just do it. An approval card appears: Allow, or Deny. A quick thumbs up or thumbs down works too. You choose each bot's approval level, from 'ask me every time' to more freedom for bots you trust. The Inspector shows every tool call the bot made. Secrets live in the encrypted Vault, and bots only get one-time references, never the real value. Need everything to stop? Pause one bot, a whole department, or everyone, in one click."
- **Visuals:**
  - Spotlight the approval card. The Allow button pulses, with a soft click.
  - Callouts for the levels, the Inspector, the Vault and pause.
  - End with the chips: "Approvals · Levels · Inspector · Vault · Pause".
- **Shots:**
  - `4.1` approval card in the chat (still + short clip of clicking Allow)
  - `4.2` approval level setting
  - `4.3` Inspector view
  - `4.4` Vault screen (no real secrets visible)
  - `4.5` pause menu

#### Scene 05: Tools, skills and memory (1:20)
- **VO:** "Bots get their power from tools. In Plugins, you add our internal MCP servers, like Jira, Confluence, Bitbucket and Zephyr, and choose which tools each bot can use. Fewer tools means faster, more focused bots. If you already have Claude Code skills and MCP servers, one switch shares them with your bots. Skills are written playbooks a bot follows for a specific job. Type slash-learn, and OMB saves what the bot just did as a new skill. And every bot has memory: plain files you can read and edit, with one-click undo, and you can turn memory off for any bot."
- **Visuals:** shots with callouts. Animate the "fewer tools = faster" idea with a long tool list shrinking to 6 items.
- **Shots:**
  - `5.1` Plugins → MCP servers list showing our servers
  - `5.2` Add server dialog
  - `5.3` per-bot tool selection
  - `5.4` the "Also use my Claude Code skills / MCP servers" switches
  - `5.5` a skill's page
  - `5.6` `/learn` in the chat (clip)
  - `5.7` memory editor

---

### CHAPTER 3: REAL WORKFLOWS

Each workflow opens with a `ChapterCard`: **title · who it's for · the daily problem**. Show the user's prompt as a `TypeOn` overlay above the chat recording, so it's readable. At the end of each workflow, show a strip of `FeatureChips` for the capabilities it used.

#### Scene 06: Workflow: Jira ticket triage, one bot (1:15)
- **Card:** "Jira triage · QA · New tickets pile up every morning"
- **Prompt:** *"Go over the new tickets in project QA from the last 24 hours. Classify each one, find duplicates, and draft a triage comment for each. Don't post anything yet."*
- **VO:** "Let's start simple: one bot, one job. Our QA triage bot reads the new Jira tickets, classifies them, spots duplicates, and drafts a comment for each one. Notice: it drafts, it doesn't post. When you're happy, you say 'post them', and an approval card appears before anything is written to Jira. Tomorrow you just say 'check again', and the bot remembers which project and rules you care about."
- **Chips:** One bot · Jira MCP · Drafts first · Approval · Memory
- **Shots:**
  - `6.1` prompt sent + bot working (clip)
  - `6.2` result table in the chat
  - `6.3` "post them" → approval card (clip)
  - `6.4` next-day "check again" (clip)

#### Scene 07: Workflow: spec → test plan → Zephyr (1:15)
- **Card:** "From spec to test cases · QA · Turning a PRD into test cases takes hours"
- **Prompt:** *"Read the PRD and tech spec for feature ABC-123 in Confluence. Write a risk-based test plan, then create the test cases in Zephyr."*
- **VO:** "Next, a QA classic. The bot pulls the PRD and the tech spec straight from Confluence, writes a risk-based test plan, and then creates the test cases in Zephyr. Before it writes anything to Zephyr, you approve. One input, a full test package out, in minutes instead of hours."
- **Chips:** Confluence MCP · Zephyr MCP · Skills · Approval
- **Shots:**
  - `7.1` prompt + bot reading Confluence (clip)
  - `7.2` test plan in the chat
  - `7.3` Zephyr approval card
  - `7.4` the created test cases in Zephyr (screenshot, blurred if needed)

#### Scene 08: Workflow: developer PR flow and parallel threads (1:15)
- **Card:** "PRs at scale · Developers · Too many PRs, not enough reviewers"
- **Prompt A:** *"Implement ticket DEV-456 in this repo and open a PR in Bitbucket."*
- **Prompt B:** *"Review each of these 4 PRs in a separate thread: #101, #102, #103, #104."*
- **VO:** "For developers: the bot works in your repo, implements the ticket, and opens a pull request in Bitbucket, after your approval. Want a second opinion? Run the review on a different model. And when there's a pile of work, ask for parallel threads. Here the bot opens four threads, one per PR, and reviews them at the same time. For really big jobs, Burst splits the work into many parallel parts and brings back one merged answer."
- **Visuals:**
  - Show the thread rows appearing under the bot.
  - Animate 4 lanes running in parallel, merging into 1 for the Burst explanation.
- **Chips:** Bitbucket MCP · Working folder · Second opinion · Parallel threads · Burst
- **Shots:**
  - `8.1` implement + PR approval (clip)
  - `8.2` second-opinion thread on another model
  - `8.3` 4 threads appearing (clip)
  - `8.4` Burst plan card with Run

#### Scene 09: Workflow: the Feature Team with a Chief of Staff (2:15). The centrepiece.
- **Card:** "A whole feature team · Dev + QA + leads · Handoffs lose context"
- **The team:** our adapted *Ship Software Safely* team, in the Engineering Room.
  - 👑 Ada, Tech Lead and Chief of Staff
  - 🔎 Researcher
  - Lin, Backend
  - Rigel, QA & Release
- **Prompt:** *"@Ada, ticket ABC-123 is ready for development. The PRD and tech spec are in Confluence. Plan it and get it moving."*
- **VO:** "Now let's see a whole team. This is our feature team. Ada is the Tech Lead and the team's Chief of Staff. With her are a Researcher, Lin on the backend, and Rigel for QA and release. One message to Ada. First, she sends the Researcher to find related tickets, specs and code, so the plan is built on facts. Then she writes the plan, and hands out the work. Lin implements and prepares the pull request. At the same time, Rigel writes the test plan and creates the test cases. Every write to Bitbucket or Zephyr waits for your approval. Rigel then reviews Lin's work against the acceptance criteria. Finally, Ada brings it all together: the PR, the test cases, open risks, and a clear release verdict. One request. A team of specialists. You approve the important steps."
- **Visuals:**
  1. An intro `FlowDiagram` of the team: Ada at the top with arrows to three bots.
  2. Then the recording, with "Sent to …" lines spotlighted.
  3. A small persistent progress tracker in the corner: Research ✓ → Plan ✓ → Build ✓ / Test ✓ → Review ✓ → Summary ✓.
- **Chips:** Group room · Chief of Staff · Delegation · Parallel work · 4 MCP servers · Approvals · Different models
- **Shots:**
  - `9.1` the Engineering Room with members
  - `9.2` prompt to Ada (clip)
  - `9.3` Researcher findings
  - `9.4` Ada's plan + "Sent to Lin / Rigel" (clip)
  - `9.5` Lin's PR approval card
  - `9.6` Rigel's Zephyr approval card
  - `9.7` Rigel's review
  - `9.8` Ada's final summary
  - `9.9` departments in the sidebar (for one line on scaling)
- **Closing line (on-screen + VO tag):** "Bigger organisation? Create departments, each with its own Chief, and they work together."

#### Scene 10: Workflow: morning standup, live dashboard and voice (1:15)
- **Card:** "Daily standup · Team leads & PMs · Status meetings eat the morning"
- **Prompt:** *"Every weekday at 8:30, post the team status: what was done yesterday, what's left, and what's blocked, from Jira and Bitbucket. Remember the last run."*
- **VO:** "Some work should just happen. Tell Ada, in one sentence, to post the team's status every weekday morning: what was done, what's left, and what's blocked. OMB turns that into a routine, which you can see on the Triggers page, and the report lands in your Inbox. With 'remember the last run', each report knows what changed since yesterday. Want it visual? Ask for a live dashboard, and the card in the chat refreshes on schedule. And if you prefer to listen, the bot can read the standup aloud, using our local voice."
- **Visuals:** a calendar animation (weekday 8:30 ticks), the Inbox notification, the dashboard card, then a speaker icon with an audio waveform.
- **Note for the editor:** add a small honest tag: "ⓘ OMB must be running for routines to fire."
- **Chips:** Routine · Triggers page · Inbox · Remember last run · Live dashboard · Local voice
- **Shots:**
  - `10.1` the routine created from chat (card with Edit/Pause)
  - `10.2` Triggers calendar
  - `10.3` Inbox with the report
  - `10.4` dashboard card
  - `10.5` read-aloud (clip with audio)

#### Scene 11: Workflow: Android device control (1:10)
- **Card:** "Real devices · QA & Automation · Manual device runs are slow"
- **Prompt:** *"On the connected Android phone, open the app, run the login flow, take a screenshot of each step, and collect the logcat for the session."*
- **VO:** "OMB can also work with real devices. Connect an Android phone over USB, and the bot can tap, type, swipe and take screenshots, step by step, right in the chat. It collects the device logs for the run, so when something fails, the evidence is already there. It will never unlock a PIN. If the phone is locked, it asks you."
- **Chips:** USB Android · Phone Harness skill · Screenshots · Logs · Approvals
- **Shots:**
  - `11.1` phone connected / device detected
  - `11.2` bot running steps, screenshots appearing in the chat (clip)
  - `11.3` the logs result
  - `11.4` optional: a real-camera clip of the phone screen moving

#### Scene 12: Workflow: browser automation and computer use (1:15)
- **Card:** "Hands on the screen · Everyone · Some tools only have a web UI"
- **Prompt:** *"Open our internal test environment in the browser, log in, create a test user, and take a screenshot of the result."*
- **VO:** "Not everything has an API. OMB includes its own automation browser, so a bot can open internal web apps, click through flows, and fill in forms. When a page needs a login, the bot pauses and hands it to you: sign in yourself, click Done, and it carries on. Or it uses a saved login from the Vault, only on that site. For full desktop work, give the bot a computer: an isolated local VM, one of our Linux servers, or, if you choose to turn it on, your own machine. You can watch the bot's screen live, and take over at any moment."
- **Chips:** Built-in browser · Sign-in hand-off · Vault logins · Local VM · Live preview & takeover
- **Shots:**
  - `12.1` browser task in progress (clip)
  - `12.2` sign-in hand-off card
  - `12.3` computer panel with options
  - `12.4` live preview of a VM desktop (clip)
  - `12.5` takeover moment (clip)

---

### CHAPTER 4: GO FURTHER

#### Scene 13: Share teams and power-user tools (1:00)
- **VO:** "Built a team that works? Share it. A whole team, with its bots, Chief of Staff, rooms, playbooks and paused routines, fits in one file, and a colleague imports it in one click. For the automation people: OMB has a command line, so a script or a CI pipeline can set up a team and run a job. Each bot can have an API key, off by default. And OMB works as an MCP server, so OpenCode or Claude Code can send work to your OMB bots and read the results."
- **Visuals:**
  - A file icon "feature-team.md" flies into the app and the team appears (diagram).
  - Then a terminal mock with the two commands typing on:
    - `openmausbot team apply team.yaml`
    - `openmausbot run "Rigel" "release readiness for 4.2" --export ./out`
  - Then an MCP diagram: OpenCode → OMB → bots.
- **Shots:** `13.1` the Import team review screen · `13.2` Bot API settings (key hidden).

#### Scene 14: Three common doubts (0:50)
- Three cards, each with a question then the answer:
  1. **"I'm not an AI expert. Can I use this?"** VO: "If you can use a chat app, you can use OMB. Click New bot, or import a ready-made team."
  2. **"Is it safe to let a bot touch my systems?"** VO: "That's what approval cards are for. Start with 'ask me every time', start in an isolated VM, and computer control of your own machine is off until you turn it on."
  3. **"Where do I start?"** VO: "Small. One bot, one job. When it works every day, add the next."
- **Shots:** none.

#### Scene 15: Your first week (0:40)
- `Checklist`, ticking in sync with the VO:
  1. Install the OMB desktop app.
  2. Create one bot for the task you like least.
  3. Connect the MCP servers it needs.
  4. Keep approvals on "ask me" and watch it work.
  5. Add a routine, or move up to a team.
  6. Ask your AI focal rep for ready-made team files.
- **VO:** "Here's your first week. Install the app. Create one bot for the task you like least. Connect the tools it needs. Keep approvals on, and watch how it works. When you trust it, add a routine, or move up to a team. And talk to your AI focal rep. They have ready-made team files for your group."

#### Scene 16: Recap and outro (0:25)
- **VO:** "That's OMB: your AI team on your desktop. Real agents on our models, working alone or as a team, with you approving what matters. Start with one bot today."
- **Visuals:**
  - A fast recap of the feature chips from every chapter, flying into a grid.
  - Final card: "OMB · Part of our AI framework" plus a placeholder line `[Internal link / support channel]` for me to fill in.

---

## 6. Shot list summary (what I'll record for you)

When we start each scene, list its shot IDs back to me, with a one-line "how to capture" each:
- whether it's a still or a clip;
- what must be visible;
- the window size: record at 1920×1080 or larger, app window maximised, light or dark theme as I decide, the same for every shot.

Don't build final animation for a shot until I've supplied it; use placeholders.

---

## 7. Quality checklist before each preview

- [ ] Nothing from the Section 2 "never" list appears in VO, captions or visuals.
- [ ] Every feature claim matches Section 4.
- [ ] Captions are in sync and at most 2 lines, with on-screen text no more than ~12 words.
- [ ] Every zoom or callout points at the right element in the real screenshot.
- [ ] Sped-up parts are tagged. Sensitive data is blurred.
- [ ] The scene length is within ±10% of its target.
- [ ] It renders without errors. Tell me the render command and the output path.

**Start now:** confirm you've read the brief, set up the project, and render the storyboard preview for all scenes (title card + placeholders + captions from the VO). Then list the shots needed for Scene 00–03.
