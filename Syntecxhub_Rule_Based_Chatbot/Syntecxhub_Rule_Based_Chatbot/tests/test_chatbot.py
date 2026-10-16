"""Unit tests - run with:  python -m unittest discover -s tests -v"""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatbot import ChatBot, ConversationLogger  # noqa: E402
from chatbot.cli import run_chat  # noqa: E402
from chatbot.text_utils import normalize, tokenize  # noqa: E402

FIXED_NOW = datetime(2026, 10, 16, 15, 30, 0)


class TextUtilsTests(unittest.TestCase):
    def test_normalize_expands_contractions_and_strips_punctuation(self):
        self.assertEqual(normalize("What's UP?!"), "what is up")

    def test_special_tokens_are_protected(self):
        self.assertEqual(normalize("Explain A* search"), "explain astar search")
        self.assertEqual(normalize("what is a star?"), "what is astar")
        self.assertEqual(normalize("TF-IDF"), "tfidf")
        self.assertEqual(normalize("K-Means"), "kmeans")

    def test_tokenize_removes_stopwords_and_stems(self):
        self.assertEqual(tokenize("What are neural networks?"), ["neural", "network"])


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.bot = ChatBot(seed=1, clock=lambda: FIXED_NOW)

    def test_greetings(self):
        for msg in ("hi", "Hello!", "hey there", "Good morning", "assalamu alaikum"):
            self.assertEqual(self.bot.respond(msg).intent, "greeting", msg)

    def test_farewell_sets_exit_flag(self):
        reply = self.bot.respond("bye")
        self.assertEqual(reply.intent, "farewell")
        self.assertTrue(reply.exit)

    def test_help_and_topics(self):
        self.assertEqual(self.bot.respond("help").intent, "help")
        self.assertEqual(self.bot.respond("what can you do?").intent, "help")
        topics = self.bot.respond("topics")
        self.assertEqual(topics.intent, "topics")
        self.assertIn("Machine Learning", topics.text)

    def test_small_talk(self):
        self.assertEqual(self.bot.respond("how are you?").intent, "how_are_you")
        self.assertEqual(self.bot.respond("what is your name").intent, "bot_name")
        self.assertEqual(self.bot.respond("who created you?").intent, "bot_creator")
        self.assertEqual(self.bot.respond("tell me a joke").intent, "joke")
        self.assertEqual(self.bot.respond("thanks a lot").intent, "thanks")

    def test_time_and_date_use_clock(self):
        self.assertIn("3:30 PM", self.bot.respond("what time is it?").text)
        self.assertIn("Friday, 16 October 2026", self.bot.respond("what's the date today").text)

    def test_remembers_user_name(self):
        self.assertIn("don't know your name", self.bot.respond("what is my name?").text)
        self.assertIn("Islam", self.bot.respond("My name is islam and I like AI").text)
        self.assertEqual(self.bot.user_name, "Islam")
        self.assertIn("Islam", self.bot.respond("what is my name").text)
        self.assertIn("Islam", self.bot.respond("hello").text)

    def test_quit_only_exits_on_its_own(self):
        self.assertTrue(self.bot.respond("quit").exit)
        self.assertFalse(self.bot.respond("quit smoking tips").exit)

    def test_empty_input(self):
        self.assertEqual(self.bot.respond("   ").intent, "empty")
        self.assertEqual(self.bot.respond("???").intent, "fallback")


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.bot = ChatBot(seed=1, clock=lambda: FIXED_NOW)

    def assert_topic(self, question, entry_id):
        reply = self.bot.respond(question)
        self.assertEqual(reply.intent, f"kb:{entry_id}", f"{question!r} -> {reply.intent}")

    def test_domain_questions(self):
        self.assert_topic("What is machine learning?", "machine_learning")
        self.assert_topic("explain neural networks", "neural_network")
        self.assert_topic("what is overfitting", "overfitting")
        self.assert_topic("Tell me about A* search", "astar")
        self.assert_topic("what is a star algorithm", "astar")
        self.assert_topic("what is tf-idf?", "tfidf")
        self.assert_topic("what is the turing test", "turing_test")
        self.assert_topic("what's a chatbot?", "chatbot")
        self.assert_topic("what is a rule based chatbot", "rule_based_system")
        self.assert_topic("what is sentiment analysis", "sentiment_analysis")
        self.assert_topic("define k-means", "clustering")
        self.assert_topic("BFS", "bfs_dfs")
        self.assert_topic("difference between bfs and dfs", "bfs_dfs")
        self.assert_topic("what are the types of machine learning", "machine_learning")
        self.assert_topic("help me understand naive bayes", "naive_bayes")
        self.assert_topic("how do i prevent overfitting", "overfitting")
        self.assert_topic("can you explain how a chatbot works", "chatbot")
        self.assert_topic("hi there, tell me about nlp", "nlp")
        self.assert_topic("ai", "ai")
        self.assert_topic("what is generative ai", "generative_ai")

    def test_greeting_plus_question_answers_the_question(self):
        reply = self.bot.respond("hello, what is deep learning?")
        self.assertEqual(reply.intent, "kb:deep_learning")
        self.assertTrue(reply.text.startswith(("Hello", "Hi")))

    def test_ambiguous_question_asks_for_clarification(self):
        reply = self.bot.respond("what is learning")
        self.assertEqual(reply.intent, "kb_ambiguous")

    def test_tell_me_more_suggests_related_topics(self):
        self.bot.respond("what is machine learning?")
        reply = self.bot.respond("tell me more")
        self.assertIn("Supervised Learning", reply.text)

    def test_out_of_domain_falls_back(self):
        reply = self.bot.respond("what is the capital of France")
        self.assertEqual(reply.intent, "fallback")
        again = self.bot.respond("how tall is mount everest")
        self.assertIn("help", again.text.lower())  # tip appears after repeated misses

    def test_every_knowledge_entry_is_findable_by_its_topic(self):
        for entry in self.bot.kb.entries:
            reply = self.bot.respond(f"what is {entry['topic']}")
            self.assertEqual(reply.intent, f"kb:{entry['id']}", entry["topic"])


class LoggerTests(unittest.TestCase):
    def test_log_file_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = ConversationLogger(log_dir=Path(tmp), clock=lambda: FIXED_NOW)
            logger.add("user", "hi")
            logger.add("bot", "Hello!", intent="greeting", confidence=1.0)
            lines = logger.path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[1])["intent"], "greeting")
            self.assertIn("You: hi", logger.format_history())
            self.assertTrue(logger.export_text().exists())
            self.assertIn("Bot: Hello!", ConversationLogger.read_session(logger.path))
            self.assertEqual(ConversationLogger.latest_session(Path(tmp)), logger.path)

    def test_disabled_logger_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            logger = ConversationLogger(log_dir=Path(tmp), enabled=False)
            logger.add("user", "hi")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.assertEqual(len(logger.entries), 1)


class ConsoleSessionTests(unittest.TestCase):
    def test_full_scripted_session(self):
        script = iter(["hi", "what is machine learning?", "/history", "/bogus", "bye"])
        printed = []
        with tempfile.TemporaryDirectory() as tmp:
            logger = ConversationLogger(log_dir=Path(tmp))
            run_chat(ChatBot(seed=2), logger, input_fn=lambda _: next(script),
                     print_fn=lambda *a: printed.append(" ".join(map(str, a))))
            self.assertEqual(len(logger.entries), 6)  # 3 user + 3 bot messages
            self.assertTrue(logger.path.exists())
        output = "\n".join(printed)
        self.assertIn("Machine Learning (ML)", output)
        self.assertIn("Unknown command", output)

    def test_ctrl_d_exits_cleanly(self):
        def raise_eof(_):
            raise EOFError
        with tempfile.TemporaryDirectory() as tmp:
            run_chat(ChatBot(), ConversationLogger(log_dir=Path(tmp)), input_fn=raise_eof,
                     print_fn=lambda *a: None)


if __name__ == "__main__":
    unittest.main()
