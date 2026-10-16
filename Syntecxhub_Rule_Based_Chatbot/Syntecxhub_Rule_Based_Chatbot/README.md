# Syntecxhub_Rule_Based_Chatbot

**SyntecBot** - a simple rule-based chatbot for the **Syntecxhub Artificial Intelligence Internship (Week 2, Project 1)**.

It uses **regex pattern matching** to detect intents (greeting, help, small talk ...), answers domain
questions from a small **Artificial Intelligence knowledge base**, runs **interactively in the console**
and **logs the full conversation history** to disk.

Pure Python standard library: **no dependencies, no internet, no setup.**

## Requirements checklist

| Requirement from the task | Where it is implemented |
|---|---|
| Conversational bot using pattern matching | `chatbot/engine.py` + regex patterns in `data/intents.json` |
| Intents: greeting, help, small talk + rule responses | 22 intents in `data/intents.json` (greeting, farewell, help, thanks, jokes, time/date, name memory, mood, ...) |
| Small knowledge base for domain questions | `data/knowledge_base.json` - 34 Artificial Intelligence topics, searched in `chatbot/knowledge.py` |
| Interactive via console | `chatbot/cli.py` (`python main.py`) |
| Log conversation history | `chatbot/logger.py` - JSON Lines file per session in `logs/`, plus `/history`, `/save`, `--history` |

## Quick start

```bash
git clone https://github.com/<your-username>/Syntecxhub_Rule_Based_Chatbot.git
cd Syntecxhub_Rule_Based_Chatbot
python main.py            # or: python -m chatbot
```

Python 3.8 or newer. Nothing to install.

### Options and commands

| | |
|---|---|
| `python main.py --no-log` | chat without writing a log file |
| `python main.py --log-dir DIR` | store logs in another folder |
| `python main.py --history` | print the most recent saved conversation and exit |
| `help` / `topics` / `tell me more` | ask the bot what it can do, what it knows, or for related topics |
| `/help` `/topics` | same, as commands |
| `/history` | show this session's conversation so far |
| `/save [file]` | export the session as a readable `.txt` transcript |
| `/clear` `/exit` | clear the screen / quit (Ctrl+C and Ctrl+D also exit cleanly) |

## Example session

```text
You> hello
SyntecBot> Hello! I'm SyntecBot, a rule-based chatbot. Ask me about Artificial Intelligence, or
  type 'help' to see what I can do.
You> my name is Islam
SyntecBot> Nice to meet you, Islam! How can I help you today?
You> what is machine learning?
SyntecBot> Machine Learning (ML) is a branch of AI where algorithms learn patterns from data
  instead of being explicitly programmed. The three main types are supervised,
  unsupervised and reinforcement learning.
You> tell me more
SyntecBot> Related topics you can ask me about: Supervised Learning, Unsupervised Learning,
  Reinforcement Learning, Deep Learning.
You> explain A* search
SyntecBot> A* is an informed search algorithm that finds the shortest path by always expanding the
  node with the lowest f(n) = g(n) + h(n), where g is the cost so far and h is a
  heuristic estimate of the remaining cost. It is optimal when the heuristic is
  admissible (never overestimates).
You> hi, tell me about NLP
SyntecBot> Hi, Islam! Natural Language Processing (NLP) lets computers understand, interpret and
  generate human language. Typical tasks are tokenization, sentiment analysis,
  translation, question answering and chatbots.
You> how do I prevent overfitting?
SyntecBot> Overfitting happens when a model memorizes the training data, including its noise, and
  performs poorly on new data. Remedies: more data, simpler models, regularization,
  dropout, early stopping and cross-validation. Underfitting is the opposite: the model
  is too simple to capture the pattern.
You> what time is it
SyntecBot> The current time is 5:53 AM.
You> what is the capital of France?
SyntecBot> Sorry, I don't know about that yet. Try asking about AI topics like machine learning,
  neural networks or A* search.
You> thanks
SyntecBot> My pleasure! Let me know if you have more questions.
You> bye
SyntecBot> Bye, Islam! It was nice talking with you.
```

A real log of this conversation is in [`logs/sample_session.jsonl`](logs/sample_session.jsonl).

## How it works

```text
user text -> normalize -> intent patterns (regex, priority-ordered)
                       -> knowledge-base search (IDF-weighted keyword overlap)
                       -> fallback with "did you mean ...?" suggestions
```

1. **Normalize** - lower-case, expand contractions (`what's` -> `what is`), keep technical tokens such as `A*`, `TF-IDF`, `K-means`, strip punctuation.
2. **Intent matching** - each intent has one or more regex patterns, a priority and optional rules (`max_words`, `yield_to_kb`). The highest-priority match wins, so `quit` exits but `quit smoking tips` does not.
3. **Knowledge base** - every entry has a topic, aliases, keywords and an answer. Words are stemmed, stop-words dropped, and each entry is scored with IDF-weighted overlap (topic/alias words count most). An exact topic or alias match always wins, so `AI` returns *Artificial Intelligence* and not *Generative AI*.
4. **Smart combinations** - `hi, what is NLP?` greets *and* answers; an ambiguous question such as `what is learning` asks which topic you mean; `tell me more` suggests related topics.
5. **Context** - remembers your name (`My name is ...`) and the last topic.
6. **Fallback** - low-confidence matches produce suggestions; repeated misses add a tip pointing to `help` / `topics`.

## Project structure

```text
Syntecxhub_Rule_Based_Chatbot/
├── main.py                  # launcher
├── chatbot/
│   ├── __init__.py
│   ├── __main__.py          # python -m chatbot
│   ├── cli.py               # console loop, commands, argparse
│   ├── engine.py            # ChatBot: intents + KB + fallback
│   ├── knowledge.py         # KnowledgeBase search
│   ├── logger.py            # ConversationLogger (JSONL + transcript)
│   └── text_utils.py        # normalize / tokenize / stem
├── data/
│   ├── intents.json         # intents, regex patterns, responses
│   └── knowledge_base.json  # AI knowledge base (34 topics)
├── tests/test_chatbot.py    # 21 unit tests
├── logs/                    # conversation logs (sample_session.jsonl included)
├── requirements.txt
└── README.md
```

## Extending the bot

* **New intent** - add an object to `data/intents.json` with `tag`, `patterns` (regex on the *normalized* text), `responses` and a `priority`. Responses can use `{nc}` (", Name"), `{name}`, `{bot}`, `{time}`, `{date}`.
* **New knowledge** - append an entry to `data/knowledge_base.json` (`id`, `topic`, `aliases`, `keywords`, `answer`, `related`). No code changes needed; the tests check that every topic can be found by its own name.
* **Another domain** - replace the knowledge base file with entries about your own subject.

## Log format

Each line of `logs/session_YYYYMMDD_HHMMSS.jsonl` is one message:

```json
{"time": "2026-10-16T05:53:05", "speaker": "bot", "text": "...", "intent": "kb:machine_learning", "confidence": 1.0}
```

## Run the tests

```bash
python -m unittest discover -s tests -v
```

## Submission checklist (Syntecxhub)

1. Create a GitHub repository named exactly **`Syntecxhub_Rule_Based_Chatbot`** and upload the entire source code.
2. Post your internship status on LinkedIn and mention **@Syntecxhub**.
3. Submit the repository link through the official **Submission Form** before the deadline.

## License

Released for learning purposes as part of the Syntecxhub internship program.
