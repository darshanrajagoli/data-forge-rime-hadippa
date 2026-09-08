# WhatsApp kickoff message

Copy everything between the lines and send it to the group. It is written to be
the only thing you have to say.

---

Ok team, project is built and on GitHub. Read this once, it's 2 minutes, then we're basically done.

👉 *https://github.com/darshanrajagoli/data-forge-rime-hadippa*

*What it is:* Waypoint — a voice assistant for delivery drivers. Hands on the wheel, eyes on the road, so they talk to it and it talks back. The clever bit is what happens when you *interrupt* it: normally the assistant finishes reading out an answer to a question you already changed your mind about, and worse, it can complete an action (like "mark delivered") that you just cancelled. Ours catches that and refuses it. That's the whole pitch.

*State of things:* the code is done, tested and audited three separate times. 626 tests, all passing. Nothing left to build.

*What's actually left is the human stuff we can't automate:*
1. Nobody has recorded the demo video — and the rules say *no video = not eligible.* This is the big one.
2. The code has never actually spoken out loud. Needs a free API key and one command.
3. Nobody has listened to it to check the pronunciation is right.
4. Nobody has tried following our own setup instructions from scratch.

*Three files, read them in this order:*
📄 `team/START-HERE.md` — what the project is, in plain English. Everyone reads this. 8 min.
📄 `team/WORKFLOW.md` — your exact steps, copy-paste. Find your name, do that section only.
📄 `HANDOFF.md` — the full technical explainer. You don't need to read it, but *upload it to ChatGPT/Gemini/Claude whenever you get stuck* and it'll know everything about the project.

*Lanes — all three run at the same time, nobody waits for anybody:*

🅰️ *Arrya* — get it running for real and *record the 4:30 demo video.* You've got Claude Pro so you get the hardest one. The script is written out shot by shot in `DEMO_SCRIPT.md`, literally every line you say. ~90 min. *This is the one that decides whether we're eligible at all.*

🅱️ *Akshay* — grab a free Rime key, run two commands to get the real speed numbers, then render the audio and *actually listen to it* and write down what you heard. You'll be the first person ever to hear this thing talk. ~75 min.

🅲 *Rahul* — play judge: fresh download, follow our own README exactly as written, and write down every place it's wrong or confusing. Then write up the submission. ~75 min. You need zero API keys for this one, so you can start immediately.

*Three rules, please don't break these:*
🔴 Never put an API key in any file except `.env.local`, and never paste one into a chat or an AI. It's an instant disqualification.
🔴 Never make up a number. If you didn't measure it, leave the TODO. An honest blank is fine, an invented number kills us.
🔴 Only touch the files your lane says you own — they don't overlap, so nobody can break anybody's work.

*If you get stuck* (expected, don't burn 40 min on it): open ChatGPT or Gemini, upload `HANDOFF.md` + `team/WORKFLOW.md` + whatever file you're stuck on, and there's a ready-made prompt at the bottom of `WORKFLOW.md` under "When you are stuck" — just fill in the blanks and paste it. It tells the AI you're not a programmer and to go one step at a time.

*One more thing for Arrya:* when the video's up, the YouTube link needs to go into the Deliverables table at the top of `README.md` AND `SUBMISSION.md` — both currently say `FILL:`. You can edit those straight on the GitHub website (click file → pencil icon → Commit changes). If you'd rather not, just drop the link here and Rahul will do it — but say which.

*Uploading your work:* you don't need git. Go to the GitHub link, click into the folder, `Add file` → `Upload files`, drag it in, `Commit changes`. That's it.

Ping the group when you start and when you're done. If you're stuck, say so early — there are message templates at the bottom of `WORKFLOW.md`.

Let's win this. 🚚
