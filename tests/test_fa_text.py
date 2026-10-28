"""
Tests for skills/ig-human/fa_text.py, the shared Persian text layer.

Run from the repo root, standard library only:

    python -m unittest discover -s tests
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "ig-human"))

import fa_text  # noqa: E402

Z = fa_text.ZWNJ
ZWJ = fa_text.ZWJ
RLM = "‏"


class Words(unittest.TestCase):
    def test_half_space_word_is_one_word(self):
        w = fa_text.word_re().findall(f"من امروز می{Z}خواهم شروع کنم")
        self.assertEqual(w, ["من", "امروز", f"می{Z}خواهم", "شروع", "کنم"])

    def test_harakat_stay_inside_the_word(self):
        self.assertEqual(fa_text.word_re().findall("کِتاب"), ["کِتاب"])

    def test_persian_digits_are_a_word(self):
        self.assertEqual(fa_text.word_re().findall("۱۸ میلیون"), ["۱۸", "میلیون"])

    def test_matches_the_old_ascii_pattern_on_english(self):
        # Every English number the pack has published depends on this.
        old = re.compile(r"[A-Za-z0-9$%'’-]+")
        new = fa_text.word_re("$%'’-")
        for text in ["I lost $18000 because of one missing contract.",
                     "it's 50% - no, 5-10 days, and that’s it",
                     "Hey guys, today I wanted to talk about content_strategy"]:
            self.assertEqual(new.findall(text), old.findall(text), text)

    def test_letters_match_the_old_ascii_pattern_on_english(self):
        old = re.compile(r"[A-Za-z']+")
        new = fa_text.letters_re("'")
        text = "We'd raised it 40% in 2025, and it's still 3x."
        self.assertEqual(new.findall(text), old.findall(text))


class Sentences(unittest.TestCase):
    def test_persian_question_mark_ends_a_sentence(self):
        parts = [s.strip() for s in fa_text.SENT_RE.findall("چرا این کار را کردی؟ نمی‌دانم.")]
        self.assertEqual(parts, ["چرا این کار را کردی؟", "نمی‌دانم."])


class Language(unittest.TestCase):
    def test_persian(self):
        self.assertEqual(fa_text.lang_of("امروز یک پرامپت ساده نوشتم"), "fa")

    def test_english(self):
        self.assertEqual(fa_text.lang_of("I wrote one simple prompt today"), "en")

    def test_persian_full_of_english_ai_names_is_still_persian(self):
        self.assertEqual(fa_text.lang_of("با ChatGPT و Claude یک پرامپت برای کاروسل نوشتم"), "fa")

    def test_explicit_choice_wins(self):
        self.assertEqual(fa_text.resolve_lang("en", "سلام"), "en")
        self.assertEqual(fa_text.resolve_lang("auto", "سلام"), "fa")


class Invisible(unittest.TestCase):
    def test_keeps_the_half_space_between_letters(self):
        text = f"می{Z}خواهم صرفه{Z}جویی کنم"
        out, deleted, kept = fa_text.drop_stray(text, {Z}, "fa")
        self.assertEqual(out, text)
        self.assertEqual((deleted, kept), (0, 2))

    def test_drops_a_half_space_next_to_a_space(self):
        out, deleted, _ = fa_text.drop_stray(f"کتاب{Z} خوب", {Z}, "fa")
        self.assertEqual((out, deleted), ("کتاب خوب", 1))

    def test_collapses_a_doubled_half_space(self):
        out, deleted, kept = fa_text.drop_stray(f"می{Z}{Z}خواهم", {Z}, "fa")
        self.assertEqual((out, deleted, kept), (f"می{Z}خواهم", 1, 1))

    def test_drops_a_half_space_inside_english(self):
        # Between Latin letters it is the fingerprint the humanizer exists for.
        out, deleted, _ = fa_text.drop_stray(f"hel{Z}lo", {Z}, "en")
        self.assertEqual((out, deleted), ("hello", 1))

    def test_keeps_the_joiner_inside_an_emoji(self):
        tech = f"\U0001F468{ZWJ}\U0001F4BB"            # man technologist
        out, deleted, _ = fa_text.drop_stray(f"برنامه‌نویس {tech}", {ZWJ}, "fa")
        self.assertIn(tech, out)
        self.assertEqual(deleted, 0)

    def test_drops_a_joiner_between_letters(self):
        out, deleted, _ = fa_text.drop_stray(f"ab{ZWJ}cd", {ZWJ}, "en")
        self.assertEqual((out, deleted), ("abcd", 1))

    def test_direction_marks_kept_in_persian_only(self):
        text = f"{RLM}ChatGPT را امتحان کردم"
        self.assertEqual(fa_text.drop_stray(text, {RLM}, "fa")[0], text)
        self.assertEqual(fa_text.drop_stray("hello" + RLM, {RLM}, "en")[0], "hello")

    def test_correct_persian_has_no_stray_invisibles(self):
        self.assertEqual(fa_text.stray_invisibles(f"می{Z}خواهم {RLM}AI یاد بگیرم", "fa"), 0)

    def test_a_zero_width_space_is_stray_in_any_language(self):
        self.assertEqual(fa_text.stray_invisibles("می​خواهم", "fa"), 1)


class Orthography(unittest.TestCase):
    def fix(self, text):
        return fa_text.fix_orthography(text)[0]

    def test_arabic_yeh_and_kaf(self):
        self.assertEqual(self.fix("كتاب علي"), "کتاب علی")

    def test_prefix_mi_and_nemi(self):
        self.assertEqual(self.fix("من می خواهم"), f"من می{Z}خواهم")
        self.assertEqual(self.fix("نمی دانم"), f"نمی{Z}دانم")

    def test_mi_inside_a_word_is_left_alone(self):
        self.assertEqual(self.fix("همیشه می‌گویم"), "همیشه می‌گویم")

    def test_superlative_and_plural_suffixes(self):
        self.assertEqual(self.fix("بزرگ ترین مدل"), f"بزرگ{Z}ترین مدل")
        self.assertEqual(self.fix("کتاب هایم"), f"کتاب{Z}هایم")
        self.assertEqual(self.fix("مدل ها را دیدم"), f"مدل{Z}ها را دیدم")

    def test_sentence_final_ha_is_left_alone(self):
        # Spoken emphasis, not a plural: "do not forget, ha".
        self.assertEqual(self.fix("یادت نره ها."), "یادت نره ها.")
        self.assertEqual(self.fix("یادت نره ها"), "یادت نره ها")

    def test_english_is_left_alone(self):
        text = "I might go home today."
        self.assertEqual(fa_text.fix_orthography(text), (text, []))

    def test_reports_what_it_changed(self):
        _, hits = fa_text.fix_orthography("علي می خواهد کتاب ها را بخرد")
        self.assertEqual(sorted(h["count"] for h in hits), [1, 1, 1])


class Fold(unittest.TestCase):
    def test_same_search_term_typed_three_ways(self):
        a = fa_text.fold("هوش‌مصنوعی")
        self.assertEqual(a, fa_text.fold("هوش مصنوعي"))
        self.assertEqual(a, fa_text.fold("هوش  مصنوعی"))

    def test_fold_is_lower_on_english(self):
        self.assertEqual(fa_text.fold("Client Contracts"), "client contracts")


if __name__ == "__main__":
    unittest.main()
